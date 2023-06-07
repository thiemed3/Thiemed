from odoo import fields, models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    partner_paciente = fields.Char(string="Paciente")
    partner_doctor = fields.Many2one('res.partner', string="Doctor")
    fecha_operacion = fields.Datetime(string="Fecha operacion")
    asistente_ciguria = fields.Many2one('res.users', string="Asistente cirugia", default=lambda self: self.env.user.id)
    tipo_venta = fields.Selection(
        selection=[('ventadirecta', 'VENTA DIRECTA'),
                   ('transito', 'TRANSITO'),
                   ('asistenciacirugia', 'ASISTENCIA CIRUGIA'),
                   ('consignacion', 'CONSIGNACION')],
        string='Tipo Venta')





