from odoo import fields, models, api
import json

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    cantidad_lote = fields.Char(string='Cantidad Lote', compute='_compute_cantidad_lote')


    def _prepare_invoice_line(self, **optional_values):
        res = super(SaleOrderLine, self)._prepare_invoice_line()
        for lot in self.order_id.picking_ids.move_line_ids_without_package:
            if lot.product_id.id == self.product_id.id:
                res.update({'lot_id': lot.lot_id.id})
        return res

    def _compute_cantidad_lote(self):
        for rec in self:
            cantidad_lote = {}

            move_lines = rec.move_ids.mapped('move_line_ids')
            # RECORRER LOS MOVIENMIENTOS DE LA LINEA DE VENTA Y OBTENER EL LOTE Y CANTIDAD.
            for move_line in move_lines:
                if move_line.lot_id:
                    if move_line.lot_id.name in cantidad_lote:
                        if move_line.picking_id.picking_type_code == 'outgoing':
                            cantidad_lote[move_line.lot_id.name] += move_line.qty_done
                        if move_line.picking_id.picking_type_code == 'incoming':
                            cantidad_lote[move_line.lot_id.name] -= move_line.qty_done

                    else:
                        cantidad_lote[move_line.lot_id.name] = move_line.qty_done

            # Crea una lista de las llaves que se deben eliminar
            keys_to_remove = []
            for key, value in cantidad_lote.items():
                if value == 0 or value == 0.0:
                    keys_to_remove.append(key)

            # Elimina las llaves del diccionario
            for key in keys_to_remove:
                del cantidad_lote[key]

            rec.cantidad_lote = json.dumps(cantidad_lote)











