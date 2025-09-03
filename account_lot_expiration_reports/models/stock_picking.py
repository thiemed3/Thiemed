# -*- coding: utf-8 -*-
from odoo import models, fields


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _safe_pricelist_price(self, pricelist, product, qty, partner, uom=None, date=None):
        """Obtiene precio desde la tarifa. Si falla (p.ej., falta tasa de moneda),
        cae a lst_price y trata de convertir a la moneda de la tarifa."""
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

    def _qty_in_move_uom(self, move):
        """Devuelve (qty, uom) donde qty está en move.product_uom."""
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

    def _prepare_pdf_values(self):
        prepared = super()._prepare_pdf_values()

        if not self.sale_id or not self.sale_id.pricelist_id:
            prepared['has_unit_price'] = False  
            return prepared

        pricelist = self.sale_id.pricelist_id
        partner = self.partner_id
        price_date = self.date_done or self.scheduled_date or fields.Date.context_today(self)

        line_amounts_dict = dict(prepared.get('total_line_amounts', {}))
        amount_untaxed = 0.0
        amount_tax = 0.0
        currency = self.sale_id.currency_id

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

            price_unit = self._safe_pricelist_price(
                pricelist=pricelist,
                product=product,
                qty=qty or 1.0,     
                partner=partner,
                uom=uom,
                date=price_date,
            )

            sale_lines = self.sale_id.order_line.filtered(lambda l: l.product_id == product)
            taxes = sale_lines[:1].tax_id or default_tax
            if taxes:
                tax_res = taxes.compute_all(price_unit, currency, qty or 0.0, product=product, partner=partner)
                line_untaxed = tax_res['total_excluded']
                line_total = tax_res['total_included']
            else:
                line_untaxed = price_unit * (qty or 0.0)
                line_total = line_untaxed

            la = dict(line_amounts_dict.get(move, {}))
            la['price_unit'] = price_unit
            la['total_amount'] = line_total
            line_amounts_dict[move] = la

            amount_untaxed += line_untaxed
            amount_tax += (line_total - line_untaxed)

        amount_total = amount_untaxed + amount_tax

        prepared.update({
            'total_line_amounts': line_amounts_dict,
            'amount_untaxed': amount_untaxed,
            'amount_tax': amount_tax,
            'amount_total': amount_total,
            'subtotal_neto': amount_untaxed,
            'total_iva': amount_tax,
            'total': amount_total,
            'has_unit_price': True,
        })
        return prepared
