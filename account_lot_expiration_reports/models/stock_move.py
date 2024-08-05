from odoo import fields, models, api


class StockMove(models.Model):
    _inherit = 'stock.move'

    lot_id = fields.Many2one('stock.lot', string='Lote')
