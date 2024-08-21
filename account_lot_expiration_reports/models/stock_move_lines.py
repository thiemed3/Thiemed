from odoo import fields, models, api


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    ccount_move_id = fields.Many2one('account.move', string='Factura')
    account_move_line_id = fields.Many2one('account.move.line', string='Linea de Factura')
    is_factured = fields.Boolean(string='Facturado')
