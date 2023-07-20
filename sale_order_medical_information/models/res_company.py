from odoo import fields, models, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    partner_especialista_id = fields.Many2one('res.users', string='Especialista', store=True, readonly=False)

