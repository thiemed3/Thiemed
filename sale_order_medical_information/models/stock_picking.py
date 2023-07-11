from odoo import fields, models, api, _


class StockPickingDoc(models.Model):
    _inherit = 'stock.picking'

    partner_paciente = fields.Char(string="Paciente")
    partner_doctor = fields.Many2one('res.partner', string="Doctor")
    fecha_operacion = fields.Datetime(string="Fecha operacion")
    asistente_cirugia = fields.Many2one('res.users', string="Asistente cirugia", default=lambda self: self.env.user.id)
    tipo_venta = fields.Selection(
        selection=[
                   ('ventadirecta', 'VENTA DIRECTA'),
                   ('transito', 'TRANSITO'),
                   ('asistenciacirugia', 'ASISTENCIA CIRUGIA'),
                   ('consignacion', 'CONSIGNACION')],
        string='Tipo Venta')

    l10n_cl_reference_ids = fields.One2many('l10n_cl.account.invoice.reference', 'picking_id', readonly=True,
                                            states={'draft': [('readonly', False)]}, string='Reference Records')

class AccountInvoiceReference(models.Model):
    _inherit = 'l10n_cl.account.invoice.reference'

    picking_id = fields.Many2one(
            'stock.picking',
            ondelete='cascade',
            index=True,
            copy=False,
            string="guia de despacho",
        )

