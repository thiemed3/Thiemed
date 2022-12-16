from odoo import fields, models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    partner_paciente = fields.Char(string="Paciente")
    partner_doctor = fields.Many2one('res.partner', string="Doctor")
    fecha_operacion = fields.Datetime(string="Fecha operacion")

