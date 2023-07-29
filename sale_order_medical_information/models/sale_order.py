from odoo import fields, models, api, _


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
        string='Tipo Venta', required=True)

    def _action_confirm(self):
        res = super(SaleOrder, self)._action_confirm()
        for order in self:
            for picking in order.picking_ids:
                picking.write({'partner_paciente': order.partner_paciente,
                               'partner_doctor': order.partner_doctor,
                               'fecha_operacion': order.fecha_operacion,
                               'tipo_venta': order.tipo_venta,
                               'asistente_cirugia': order.asistente_cirugia})
        return res

    def _create_invoices(self, grouped=False, final=False, date=None):
        res = super(SaleOrder, self)._create_invoices()
        for order in self:
            for invoice in order.invoice_ids:
                invoice.write({'partner_paciente': order.partner_paciente,
                               'partner_doctor': order.partner_doctor,
                               'fecha_operacion': order.fecha_operacion,
                               'tipo_venta': order.tipo_venta,
                               'asistente_cirugia': order.asistente_cirugia})
        return res

    #@api.onchange('partner_id')
    #def onchange_partner_id(self):
    #    res =  super(SaleOrder, self).onchange_partner_id()
    #    self.asistente_cirugia = self['user_id']
    #    return res

    #@api.onchange('user_id')
    #def onchange_user_id(self):
    #    res = super(SaleOrder, self).onchange_user_id()
    #    if self.user_id:
    #        self.asistente_cirugia = self['user_id']
    #    return res