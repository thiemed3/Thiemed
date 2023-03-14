from odoo import fields, models, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'


    def _prepare_invoice_line(self, **optional_values):
        res = super(SaleOrderLine, self)._prepare_invoice_line()
        res.update({'lot_id': self.order_id.picking_ids.move_line_ids_without_package.lot_id.id})
        return res


