# -*- coding: utf-8 -*-
import json
import logging

from odoo import fields, models

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
            or (self.product_id.display_name or self.product_id.name or '')
        )

        res['main_currency'] = res.get('main_currency') or self.move_id.currency_id or self.company_currency_id

        if self.display_type in ('line_section', 'line_note'):
            res['price_item_document'] = res.get('price_item_document', 0.0) or 0.0
            res['price_line_document'] = res.get('price_line_document', 0.0) or 0.0
            res['total_discount'] = 0.0
            return res

        res['price_item_document'] = res.get('price_item_document', self.price_unit or 0.0) or 0.0
        res['price_line_document'] = res.get('price_line_document', self.price_subtotal or 0.0) or 0.0

        if self.discount:
            qty = self.quantity or 0.0
            base_sin_desc = (self.price_unit or 0.0) * qty
            disc = base_sin_desc * (self.discount / 100.0)
            cur = (self.move_id.currency_id or self.company_currency_id)
            res['total_discount'] = cur.round(disc) if cur else disc
        else:
            res['total_discount'] = 0.0

        return res

    # ---------- Helper seguro para precios de lista ----------
    def _safe_pricelist_price(self, pricelist, product, qty, partner, date_ctx):
        """Devuelve el precio de lista con fecha y compañía correctas.
        Si falta tasa de moneda o cualquier error, cae a price_unit o list_price.
        """
        self.ensure_one()
        fallback = self.price_unit or product.list_price or 0.0
        if not pricelist:
            return fallback
        try:
            pl = pricelist.with_company(self.company_id).with_context(date=str(date_ctx) if date_ctx else False)
            return pl._get_product_price(product, qty or 0.0, partner)
        except Exception as e:
            _logger.warning(
                "account_lot_expiration_reports: fallback de precio para producto %s (qty=%s). "
                "Motivo: %s", product.display_name, qty, e
            )
            return fallback

    def get_lote_lines(self):
        self.ensure_one()
        detail_lines = {}
        date_ctx = self.move_id.invoice_date or fields.Date.context_today(self)
        uom_factura = self.product_uom_id

        # ¿Es kit fantasma?
        is_kit = self.product_id.bom_ids.filtered(lambda b: b.type == 'phantom')[:1]

        # Movimientos entregados
        delivered_move_lines = (
            self.mapped('sale_line_ids.move_ids')
            .mapped('move_line_ids')
            .filtered(lambda ml: ml.state == 'done')
        )

        # ------------------------ KITS ------------------------
        if is_kit and delivered_move_lines:
            sale_order = self.sale_line_ids[:1].order_id
            pricelist = sale_order.pricelist_id if sale_order else False
            partner = sale_order.partner_id if sale_order else self.move_id.partner_id

            # ratio: prorrateo segun facturado vs entregado
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
                    kits_delivered_candidates.append(total_comp / bl.product_qty)

            kits_delivered = min(kits_delivered_candidates) if kits_delivered_candidates else 0.0
            kits_invoiced = self.quantity or 0.0
            ratio = min(1.0, (kits_invoiced / kits_delivered)) if kits_delivered > 0 else 1.0

            # AGRUPAR por (producto + lote), y omitir cantidades <= 0
            for ml in delivered_move_lines:
                component = ml.product_id
                lot = ml.lot_id
                qty_base = (getattr(ml, 'qty_done', 0.0) or getattr(ml, 'quantity', 0.0)) or 0.0
                qty_base *= ratio
                if qty_base <= 0:
                    continue  # << evita filas 0 un

                key = f"{component.id}:{(lot.name or 'SIN LOTE')}"
                if key not in detail_lines:
                    detail_lines[key] = {
                        'component_code': component.default_code or '',
                        'component_name': component.display_name or component.name or '',
                        'cantidad': 0.0,
                        'nombre': lot.name if lot else '',
                        'fecha_vencimiento': lot.expiration_date.strftime('%d/%m/%Y') if (lot and lot.expiration_date) else '',
                        'udm': ml.product_uom_id.name,
                        # El PDF muestra price_unit de la línea en el primer lote; este precio es informativo.
                        'precio': self._safe_pricelist_price(pricelist, component, qty_base, partner, date_ctx),
                    }
                detail_lines[key]['cantidad'] += qty_base

        # ------------------ NO KITS (producto normal) ------------------
        if not detail_lines:
            if delivered_move_lines:
                remaining = float(self.quantity or 0.0)
                for ml in delivered_move_lines:
                    if ml.product_id != self.product_id:
                        continue
                    if remaining <= 0:
                        break

                    lot = ml.lot_id
                    qty_base = (getattr(ml, 'qty_done', 0.0) or getattr(ml, 'quantity', 0.0)) or 0.0
                    qty_in_invoice_uom = ml.product_uom_id._compute_quantity(
                        qty_base, uom_factura, rounding_method='HALF-UP'
                    )
                    take = min(qty_in_invoice_uom, remaining)
                    if take <= 0:
                        continue  # << evita filas 0 un
                    remaining -= take

                    key = f"{self.product_id.id}:{(lot.name or 'SIN LOTE')}"
                    if key not in detail_lines:
                        detail_lines[key] = {
                            'component_code': self.product_id.default_code or '',
                            'component_name': self.product_id.display_name or self.product_id.name or '',
                            'cantidad': 0.0,
                            'nombre': lot.name if lot else '',
                            'fecha_vencimiento': lot.expiration_date.strftime('%d/%m/%Y') if (lot and lot.expiration_date) else '',
                            'udm': uom_factura.name,
                            'precio': self.price_unit,
                        }
                    detail_lines[key]['cantidad'] += take
            else:
                # sin movimientos: una sola fila "simple"
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
