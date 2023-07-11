from odoo import fields, models, api, _


class StockPickingDoc(models.Model):
    _inherit = 'stock.picking'

    l10n_cl_reference_ids = fields.One2many('l10n_cl.account.invoice.reference', 'picking_id', readonly=False, string='Reference Records')

class AccountInvoiceReference(models.Model):
    _inherit = 'l10n_cl.account.invoice.reference'

    picking_id = fields.Many2one(
            'stock.picking',
            ondelete='cascade',
            index=True,
            copy=False,
            string="guia de despacho",
        )

