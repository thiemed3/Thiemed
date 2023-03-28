from odoo import fields, models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    partner_paciente = fields.Char(string="Paciente", readonly=True)
    partner_doctor = fields.Many2one('res.partner', string="Doctor", readonly=True)
    fecha_operacion = fields.Datetime(string="Fecha operacion", readonly=True)
    tipo_venta = fields.Selection(
        selection=[('ventadirecta', 'VENTA DIRECTA'),
                   ('transito', 'TRANSITO'),
                   ('asistenciacirugia', 'ASISTENCIA CIRUGIA'),
                   ('consignacion', 'CONSIGNACION')],
        string='Tipo Venta', required=True, default='ventadirecta')



