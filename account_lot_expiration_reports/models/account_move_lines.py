from odoo import fields, models, api


class AccountMoveLines(models.Model):
    _inherit = 'account.move.line'

    lot_id = fields.Many2one('stock.production.lot', string='Lote', store=True, readonly=False, compute='get_lot_product')


    def get_lot_product(self):
        sales = self.env['sale.order'].search([('invoice_ids', '=', self.move_id.id)])
        for lots in sales.picking_ids.move_line_ids_without_package:
            if lots.product_id.id == self.product_id.id:
                self.lot_id = lots.lot_id.id
