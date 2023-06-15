from odoo import fields, models, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    account_move_id = fields.Many2one('account.move', string='Factura', copy=False)



