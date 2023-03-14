from odoo import fields, models, api


class AccountMoveLines(models.Model):
    _inherit = 'account.move.line'

    lot_id = fields.Many2one('stock.production.lot', string='Lote', store=True)
