# -*- coding: utf-8 -*-
from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _prepare_pdf_values(self):
        prepared_amounts = super(StockPicking, self)._prepare_pdf_values()

        if not self.sale_id or not self.sale_id.pricelist_id:
            return prepared_amounts

        pricelist = self.sale_id.pricelist_id

        line_amounts_dict = prepared_amounts.get('total_line_amounts', {}).copy()

        new_amount_untaxed = 0.0

        for move in self.move_ids_without_package:
            if not move.product_id:
                continue

            product = move.product_id
            partner = self.partner_id
            price_unit = pricelist._get_product_price(product, move.product_uom_qty, partner)
            line_amounts = line_amounts_dict.get(move, {})
            line_amounts['price_unit'] = price_unit
            line_amounts['total_amount'] = price_unit * move.quantity
            new_amount_untaxed += line_amounts['total_amount']
            line_amounts_dict[move] = line_amounts

        # --- AJUSTE FINAL Y DEFINITIVO PARA LOS TOTALES ---
        prepared_amounts['total_line_amounts'] = line_amounts_dict
        taxes = self.sale_id.order_line.mapped('tax_id')
        tax = taxes[0] if taxes else self.env['account.tax'].search([
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.company_id.id),
            ('amount', '=', 19)
        ], limit=1)

        new_taxes = 0.0
        if tax:
            tax_calculation = tax.compute_all(new_amount_untaxed, self.sale_id.currency_id, 1, product=None,
                                              partner=self.partner_id)
            new_amount_total = tax_calculation['total_included']
            new_taxes = tax_calculation['total_excluded'] - new_amount_untaxed if tax.price_include else \
            tax_calculation['taxes'][0]['amount'] if tax_calculation['taxes'] else 0.0
        else:
            new_amount_total = new_amount_untaxed

        prepared_amounts['amount_untaxed'] = new_amount_untaxed
        prepared_amounts['amount_tax'] = new_taxes
        prepared_amounts['amount_total'] = new_amount_total
        prepared_amounts['subtotal_neto'] = new_amount_untaxed
        prepared_amounts['total_iva'] = new_taxes
        prepared_amounts['total'] = new_amount_total

        return prepared_amounts