# -*- coding: utf-8 -*-
from odoo import models, fields
from odoo.tools import float_repr 


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _l10n_cl_get_tax_amounts(self):
        """
        Recalcula totales y montos por línea para el DTE usando:
        - Pedido de venta (precio/desc/impuestos) cuando aplica
        - Si partner tiene "none", forzamos product o sale_order (según disponibilidad/moneda)
        - Manejo de kits: componentes usan tarifa del componente
        Devuelve (totals, retentions, line_amounts).
        """
        totals = {
            'vat_amount': 0.0,
            'subtotal_amount_taxable': 0.0,
            'subtotal_amount_exempt': 0.0,
            'vat_percent': False,
            'total_amount': 0.0,
        }
        retentions = {}
        line_amounts = {}

        partner = self.partner_id
        company = self.company_id
        currency = company.currency_id

        # --- Política de precio para guía ---
        guide_price = partner.l10n_cl_delivery_guide_price
        if guide_price == 'none':
            guide_price = "sale_order" if (self.sale_id and self.sale_id.currency_id == currency) else "product"
        if guide_price == 'sale_order' and (not self.sale_id or self.sale_id.currency_id != currency):
            guide_price = 'product'

        max_vat_perc = 0.0
        tax_group_ila = self.env['account.chart.template'].with_company(company).ref(
            'tax_group_ila', raise_if_not_found=False
        )
        tax_group_ret = self.env['account.chart.template'].with_company(company).ref(
            'tax_group_retenciones', raise_if_not_found=False
        )
        TAX19_SII_CODE = 14

        for move in self.move_ids.filtered(lambda m: m.quantity > 0):
            product = move.product_id
            if not product:
                continue

            qty, uom = self._qty_in_move_uom(move)
            qty = qty or 0.0

            sol = move.sale_line_id or (
                self.sale_id.order_line.filtered(lambda l: l.product_id == product)[:1] if self.sale_id else False
            )
            is_kit_component = bool(getattr(move, 'bom_line_id', False))

            if is_kit_component:
                if self.sale_id and self.sale_id.pricelist_id:
                    price_unit = self._safe_pricelist_price(
                        pricelist=self.sale_id.pricelist_id,
                        product=product, qty=qty or 1.0, partner=partner, uom=uom,
                        date=(self.date_done or self.scheduled_date or fields.Date.context_today(self)),
                    )
                else:
                    price_unit = product.uom_id._compute_price(product.lst_price, uom)
                discount = float(sol.discount or 0.0) if sol else 0.0
                taxes = (sol.tax_id if sol else product.taxes_id).filtered(lambda t: t.company_id == company)
            else:
                if guide_price == 'sale_order' and sol:
                    price_unit = sol.product_uom._compute_price(sol.price_unit, uom)
                    discount = float(sol.discount or 0.0)
                    taxes = sol.tax_id
                else:
                    price_unit = product.uom_id._compute_price(product.lst_price, uom)
                    discount = 0.0
                    taxes = product.taxes_id.filtered(lambda t: t.company_id == company)

            price_after_disc = price_unit * (1 - (discount or 0.0) / 100.0)
            if taxes:
                tax_res = taxes.compute_all(price_after_disc, currency=currency, quantity=qty, partner=partner)
            else:
                base = price_after_disc * qty
                tax_res = {'total_excluded': base, 'total_included': base, 'taxes': []}

            totals['total_amount'] += tax_res['total_included']

            no_vat_taxes = True
            for tax_val in tax_res.get('taxes', []):
                tax = self.env['account.tax'].browse(tax_val['id'])
                if tax.l10n_cl_sii_code == TAX19_SII_CODE:
                    no_vat_taxes = False
                    totals['vat_amount'] += tax_val['amount']
                    max_vat_perc = max(max_vat_perc, tax.amount)
                elif tax.tax_group_id and (
                    (tax_group_ila and tax.tax_group_id.id == tax_group_ila.id) or
                    (tax_group_ret and tax.tax_group_id.id == tax_group_ret.id)
                ):
                    key = (tax.l10n_cl_sii_code, tax.amount, tax.tax_group_id.name)
                    retentions.setdefault(key, 0.0)
                    retentions[key] += tax_val['amount']

            if no_vat_taxes:
                totals['subtotal_amount_exempt'] += tax_res['total_excluded']
            else:
                totals['subtotal_amount_taxable'] += tax_res['total_excluded']

            undisc_unit_excl = price_unit
            disc_unit_excl = (tax_res['total_excluded'] / qty) if qty else price_after_disc
            line_amounts[move] = {
                "value": currency.round(tax_res['total_included']),
                "total_amount": currency.round(tax_res['total_excluded']),
                "price_unit": currency.round(undisc_unit_excl),
                "price_unit_disc": currency.round(disc_unit_excl),
                "exempt": no_vat_taxes and (tax_res['total_excluded'] != 0.0),
            }
            if discount:
                if taxes:
                    tax_res_undisc = taxes.compute_all(price_unit, currency=currency, quantity=qty, partner=partner)
                    base_undisc = tax_res_undisc['total_excluded']
                else:
                    base_undisc = price_unit * qty
                disc_amount = base_undisc * discount / 100.0
                line_amounts[move].update({
                    'discount': discount,
                    'total_discount': float_repr(currency.round(disc_amount), 0),
                    'total_discount_fl': currency.round(disc_amount),
                })

        totals['vat_percent'] = max_vat_perc and float_repr(max_vat_perc, 2) or False
        retention_res = [
            {
                'tax_code': code,
                'tax_percent': percent,
                'tax_name': name,
                'tax_amount': currency.round(amount),
            }
            for (code, percent, name), amount in retentions.items()
        ]
        return totals, retention_res, line_amounts

    # ---------- Helper: precio por tarifa con uom/fecha y fallback ---------- #
    def _safe_pricelist_price(self, pricelist, product, qty, partner, uom=None, date=None):
        """Obtiene precio desde la tarifa con UoM/fecha. Si falla, cae a lst_price convertido si se puede."""
        date = fields.Date.to_date(date) or fields.Date.context_today(self)
        uom = uom or product.uom_id
        try:
            return pricelist._get_product_price(product, qty, partner, uom=uom, date=date)
        except Exception:
            price = product.lst_price
            try:
                company = self.company_id
                from_cur = company.currency_id
                to_cur = pricelist.currency_id
                if from_cur and to_cur and from_cur != to_cur:
                    price = from_cur._convert(price, to_cur, company, date, round=False)
            except Exception:
                pass
            return price

    # ---------- Helper: cantidad en la UoM del move (suma de move lines) ---------- #
    def _qty_in_move_uom(self, move):
        """Devuelve (qty, uom) donde qty está expresada en la UoM del move."""
        move_uom = move.product_uom
        if move.state == 'done':
            qty = 0.0
            for ml in move.move_line_ids:
                if not ml.qty_done:
                    continue
                qty += ml.product_uom_id._compute_quantity(
                    ml.qty_done, move_uom, rounding_method='HALF-UP'
                )
            return qty or 0.0, move_uom
        return (move.product_uom_qty or 0.0), move_uom

    # ---------- PDF: reutiliza los mismos montos que el DTE ---------- #
    def _prepare_pdf_values(self):
        amounts, withholdings, total_line_amounts = self._l10n_cl_get_tax_amounts()
        res = super()._prepare_pdf_values()
        res.update({
            'amounts': amounts,
            'withholdings': withholdings,
            'total_line_amounts': total_line_amounts,
            'has_unit_price': any(l.get('price_unit', 0.0) != 0.0 for l in total_line_amounts.values()),
            'has_discount': any(l.get('total_discount', '0') != '0' for l in total_line_amounts.values()),
            'amount_untaxed': amounts['subtotal_amount_taxable'] + amounts['subtotal_amount_exempt'],
            'amount_tax': amounts['vat_amount'],
            'amount_total': amounts['total_amount'],
        })
        return res
