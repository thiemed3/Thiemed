from odoo import fields, models, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'


    def _prepare_invoice_line(self, **optional_values):
        res = super(SaleOrderLine, self)._prepare_invoice_line()
        for lot in self.order_id.picking_ids.move_line_ids_without_package:
            if lot.product_id.id == self.product_id.id:
                res.update({'lot_id': lot.lot_id.id})
        return res


