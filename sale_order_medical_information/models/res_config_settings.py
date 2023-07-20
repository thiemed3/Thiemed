from odoo import fields, models, api


class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    partner_especialista_id = fields.Many2one('res.users', string='Especialista', related='company_id.partner_especialista_id', store=True, readonly=False)


