from odoo import fields, models, api, _


class StockPickingDoc(models.Model):
    _inherit = 'stock.picking'

    partner_paciente = fields.Char(string="Paciente")
    partner_doctor = fields.Many2one('res.partner', string="Doctor")
    fecha_operacion = fields.Datetime(string="Fecha operacion")

    