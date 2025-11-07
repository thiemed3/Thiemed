# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools import float_round, float_repr
import json

import logging
_logger = logging.getLogger(__name__)

class AccountMoveLines(models.Model):
    _inherit = 'account.move.line'

    cantidad_lote = fields.Char(string='Cantidad Lote')

    def _l10n_cl_get_line_amounts(self):
        self.ensure_one()
        res = super()._l10n_cl_get_line_amounts()

        res['line_description'] = (
            res.get('line_description')
            or self.name
            or (self.product_id.display_name or self.product_id.name or ''))
            
        res['main_currency'] = res.get('main_currency') or self.move_id.currency_id or self.company_currency_id

        if self.display_type in ('line_section', 'line_note'):
            res['price_item_document'] = res.get('price_item_document', 0.0) or 0.0
            res['price_line_document'] = res.get('price_line_document', 0.0) or 0.0
            res['total_discount'] = 0.0
            return res

        res['price_item_document'] = (
            res.get('price_item_document', self.price_unit or 0.0) or 0.0)
        res['price_line_document'] = (
            res.get('price_line_document', self.price_subtotal or 0.0) or 0.0)

        if self.discount:
            qty = self.quantity or 0.0
            base_sin_desc = (self.price_unit or 0.0) * qty
            disc = base_sin_desc * (self.discount / 100.0)
            cur = (self.move_id.currency_id or self.company_currency_id)
            res['total_discount'] = cur.round(disc) if cur else disc
        else:
            res['total_discount'] = 0.0

        return res

    def get_lote_lines(self):
        self.ensure_one()

        date_to_use = self.move_id.invoice_date or self.move_id.date or fields.Date.context_today(self)

        detail_lines = {}

        is_kit = self.product_id.bom_ids.filtered(lambda b: b.type == 'phantom')[:1]
        delivered_move_lines = (
            self.mapped('sale_line_ids.move_ids')
            .mapped('move_line_ids')
            .filtered(lambda ml: ml.state == 'done')
        )

        if is_kit and delivered_move_lines:
            sale_order = self.sale_line_ids[:1].order_id
            pricelist = sale_order.pricelist_id if sale_order else False
            partner = sale_order.partner_id if sale_order else self.move_id.partner_id

            kits_delivered_candidates = []
            for bl in is_kit.bom_line_ids:
                total_comp = 0.0
                for ml in delivered_move_lines.filtered(lambda m: m.product_id == bl.product_id):
                    if not ml.qty_done:
                        continue
                    total_comp += ml.product_uom_id._compute_quantity(
                        ml.qty_done, bl.product_uom_id, rounding_method='HALF-UP'
                    )
                if bl.product_qty > 0:
                    kits_eq = total_comp / bl.product_qty
                    kits_delivered_candidates.append(kits_eq)

            kits_delivered = min(kits_delivered_candidates) if kits_delivered_candidates else 0.0
            kits_invoiced = self.quantity  
            ratio = 1.0
            if kits_delivered > 0:
                ratio = min(1.0, kits_invoiced / kits_delivered)

            for move_line in delivered_move_lines:
                component = move_line.product_id
                lot = move_line.lot_id
                qty_base = (getattr(move_line, 'qty_done', 0.0) or getattr(move_line, 'quantity', 0.0)) or 0.0
                qty_base *= ratio

                price = component.list_price

                if pricelist:
                    if pricelist.company_id:
                        company_to_use = self.move_id.company_id
                        price = pricelist.with_company(company_to_use)._get_product_price(
                            component, qty_base, partner, date=date_to_use
                        )
                    else:
                        _logger.warning(
                            f"ADVERTENCIA: La tarifa '{pricelist.name}' no tiene compañía asignada"
                            f" No se puede calcular el precio del componente '{component.default_code}'."
                            f" Usando 'list_price' ({price}) como respaldo."
                        )
                        

                key = f"ml-kit-{move_line.id}"
                detail_lines[key] = {
                    'component_code': component.default_code or '',
                    'component_name': component.display_name or component.name or '',
                    'cantidad': qty_base,
                    'nombre': lot.name if lot else '',
                    'fecha_vencimiento': lot.expiration_date.strftime('%d/%m/%Y') if (
                            lot and lot.expiration_date) else '',
                    'udm': move_line.product_uom_id.name,
                    'precio': price, 
                }

        if not detail_lines:
            uom_factura = self.product_uom_id

            if delivered_move_lines:
                remaining = float(self.quantity or 0.0)

                for move_line in delivered_move_lines:
                    if move_line.product_id != self.product_id:
                        continue
                    if remaining <= 0:
                        break

                    lot = move_line.lot_id
                    key = lot.name if lot else 'SIN LOTE'
                    qty_base = (getattr(move_line, 'qty_done', 0.0) or getattr(move_line, 'quantity', 0.0)) or 0.0

                    qty_in_invoice_uom = move_line.product_uom_id._compute_quantity(
                        qty_base, uom_factura, rounding_method='HALF-UP'
                    )

                    take = min(qty_in_invoice_uom, remaining)
                    if take <= 0:
                        continue
                    remaining -= take

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
                    detail_lines[key]['cantidad'] += take

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
