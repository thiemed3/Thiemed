# -*- coding: utf-8 -*-
from odoo import fields, models, api


class AccountMoveLines(models.Model):
    _inherit = 'account.move.line'

    cantidad_lote = fields.Char(string='Cantidad Lote')

    def _l10n_cl_get_line_amounts(self):
        res = super()._l10n_cl_get_line_amounts()
        if 'line_description' not in res:
            res['line_description'] = self.name
        return res

    def get_lote_lines(self):
        self.ensure_one()
        detail_lines = {}

        is_kit = self.product_id.bom_ids.filtered(lambda b: b.type == 'phantom')
        delivered_move_lines = (
            self.mapped('sale_line_ids.move_ids')
            .mapped('move_line_ids')
            .filtered(lambda ml: ml.state == 'done')
        )

        if is_kit and delivered_move_lines:
            sale_order = self.sale_line_ids[:1].order_id
            pricelist = sale_order.pricelist_id if sale_order else False
            partner = sale_order.partner_id if sale_order else self.move_id.partner_id

            for move_line in delivered_move_lines:
                component = move_line.product_id
                lot = move_line.lot_id
                qty_base = getattr(move_line, 'qty_done', 0.0) or getattr(move_line, 'quantity', 0.0)
                price = (
                    pricelist._get_product_price(component, qty_base, partner)
                    if pricelist else component.list_price
                )
                key = f"ml-kit-{move_line.id}"
                detail_lines[key] = {
                    'component_code': component.default_code or '',
                    'component_name': component.display_name or component.name or '',
                    'cantidad': qty_base,  # UoM del movimiento del componente
                    'nombre': lot.name if lot else '',
                    'fecha_vencimiento': lot.expiration_date.strftime('%d/%m/%Y') if (
                                lot and lot.expiration_date) else '',
                    'udm': move_line.product_uom_id.name,
                    'precio': price,
                }

        if not detail_lines:
            uom_factura = self.product_uom_id

            if delivered_move_lines:
                for move_line in delivered_move_lines:
                    if move_line.product_id != self.product_id:
                        continue

                    lot = move_line.lot_id
                    key = lot.name if lot else 'SIN LOTE'
                    qty_base = getattr(move_line, 'qty_done', 0.0) or getattr(move_line, 'quantity', 0.0)

                    cantidad_en_udm_factura = move_line.product_uom_id._compute_quantity(
                        qty_base, uom_factura, rounding_method='HALF-UP'
                    )

                    detail_lines.setdefault(key, {
                        'component_code': self.product_id.default_code or '',
                        'component_name': self.product_id.display_name or self.product_id.name or '',
                        'cantidad': 0.0,
                        'nombre': '' if key == 'SIN LOTE' else key,
                        'fecha_vencimiento': lot.expiration_date.strftime('%d/%m/%Y') if (
                                    lot and lot.expiration_date) else '',
                        'udm': uom_factura.name,
                        'precio': self.price_unit,
                    })
                    detail_lines[key]['cantidad'] += cantidad_en_udm_factura

            else:
                detail_lines['main'] = {
                    'component_code': self.product_id.default_code or '',
                    'component_name': self.product_id.display_name or self.product_id.name or '',
                    'cantidad': self.quantity,
                    'nombre': '',
                    'fecha_vencimiento': '',
                    'udm': uom_factura.name,
                    'precio': self.price_unit,
                }

        return detail_lines


    def only_name(self, name):
        if name and ']' in name:
            return name.split(']')[1]
        return name

    def only_code(self, name):
        if name and ']' in name:
            return name.split(']')[0].replace('[', '')
        return name
