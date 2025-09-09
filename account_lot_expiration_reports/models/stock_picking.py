# -*- coding: utf-8 -*-
from odoo import models, fields


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # ---------- Helper: precio por tarifa con uom/fecha y fallback ---------- #
    def _safe_pricelist_price(self, pricelist, product, qty, partner, uom=None, date=None):
        """Obtiene precio desde la tarifa con UoM/fecha.
        Si falla (p. ej. por tasas), cae a lst_price convertido si se puede."""
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

    # ---------- Preparación de valores para la guía (con kits) ---------- #
    def _prepare_pdf_values(self):
        prepared = super()._prepare_pdf_values()

        if not self.sale_id:
            prepared['has_unit_price'] = False
            return prepared

        partner = self.partner_id
        currency = self.sale_id.currency_id
        pricelist = self.sale_id.pricelist_id
        price_date = self.date_done or self.scheduled_date or fields.Date.context_today(self)

        line_amounts_dict = dict(prepared.get('total_line_amounts', {}))
        amount_untaxed = 0.0
        amount_tax = 0.0

        default_tax = self.env['account.tax'].search([
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.company_id.id),
            ('amount', '=', 19),
        ], limit=1)

        for move in self.move_ids_without_package:
            product = move.product_id
            if not product:
                continue

            qty, uom = self._qty_in_move_uom(move)

            sol = move.sale_line_id or self.sale_id.order_line.filtered(
                lambda l: l.product_id == product
            )[:1]

            is_kit_component = bool(getattr(move, 'bom_line_id', False))

            if is_kit_component:
                if pricelist:
                    price_unit = self._safe_pricelist_price(
                        pricelist=pricelist,
                        product=product,
                        qty=qty or 1.0,
                        partner=partner,
                        uom=uom,
                        date=price_date,
                    )
                else:
                    price_unit = product.uom_id._compute_price(product.lst_price, uom)
                discount = float(sol.discount) if sol else 0.0
                taxes = sol.tax_id or default_tax
            else:
                if sol:
                    price_unit = sol.product_uom._compute_price(sol.price_unit, uom)
                    discount = float(sol.discount or 0.0)
                    taxes = sol.tax_id or default_tax
                else:
                    price_unit = product.uom_id._compute_price(product.lst_price, uom)
                    discount = 0.0
                    taxes = default_tax

            price_after_disc = price_unit * (1 - discount / 100.0)
            if taxes:
                tax_res = taxes.compute_all(price_after_disc, currency, qty or 0.0,
                                            product=product, partner=partner)
                line_untaxed = tax_res['total_excluded']
                line_total = tax_res['total_included']
            else:
                line_untaxed = price_after_disc * (qty or 0.0)
                line_total = line_untaxed

            # Actualizar estructura
            la = dict(line_amounts_dict.get(move, {}))
            la['price_unit'] = price_unit
            la['discount'] = discount
            la['total_amount'] = line_untaxed
            line_amounts_dict[move] = la

            amount_untaxed += line_untaxed
            amount_tax += (line_total - line_untaxed)

        prepared.update({
            'total_line_amounts': line_amounts_dict,
            'amount_untaxed': amount_untaxed,
            'amount_tax': amount_tax,
            'amount_total': amount_untaxed + amount_tax,
            'subtotal_neto': amount_untaxed,
            'total_iva': amount_tax,
            'total': amount_untaxed + amount_tax,
            'has_unit_price': True,
        })
        return prepared
