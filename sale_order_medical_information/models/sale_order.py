from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    partner_paciente = fields.Char(string="Paciente")
    partner_doctor = fields.Many2one('res.partner', string="Doctor")
    fecha_operacion = fields.Datetime(string="Fecha operacion")
    asistente_cirugia = fields.Many2one('res.users', string="Asistente cirugia", )#default=lambda self: self.env.user)
    tipo_venta = fields.Selection(
        selection=[('ventadirecta', 'VENTA DIRECTA'),
                   ('transito', 'TRANSITO'),
                   ('asistenciacirugia', 'ASISTENCIA CIRUGIA'),
                   ('consignacion', 'CONSIGNACION')],
        string='Tipo Venta', required=False)

    def _action_confirm(self):
        res = super()._action_confirm()
        for order in self:
            for picking in order.picking_ids:
                picking.write(order._get_medical_information_values())
        return res

    def _prepare_invoice(self):
        values = super()._prepare_invoice()
        values.update(self._get_medical_information_values())
        return values

    def _get_medical_information_values(self):
        self.ensure_one()
        return {
            'partner_paciente': self.partner_paciente,
            'partner_doctor': self.partner_doctor.id,
            'fecha_operacion': self.fecha_operacion,
            'tipo_venta': self.tipo_venta,
            'asistente_cirugia': self.asistente_cirugia.id,
        }
