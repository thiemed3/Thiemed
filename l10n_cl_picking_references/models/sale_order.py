from odoo import fields, models, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    date_dte = fields.Date(string='Fecha referencia', readonly=True)
