from odoo import models, api
from odoo.exceptions import UserError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def create(self, vals):
        res = super(SaleOrder, self).create(vals)
        # creamos el analytic account con el nombre del pedido de venta
        analityc = self.env['account.analytic.account'].create({
            'name': res.name + ' - ' + res.partner_id.name,
            'partner_id': res.partner_id.id,
            'code': res.name,
            'active': True,
        })
        # asignamos el analytic account al pedido de venta
        res.analytic_account_id = analityc.id

        return res

    def action_cancel(self):
        res = super(SaleOrder, self).action_cancel()
        # eliminamos el analytic account
        self.analytic_account_id.active = False
        return res

    def action_draft(self):
        res = super(SaleOrder, self).action_draft()
        # activamos el analytic account
        self.analytic_account_id.active = True
        return res

    @api.onchange('analytic_account_id')
    def _onchange_analytic_account_id(self):
        # no se puede eliminar la cuenta analitica
        if not self.analytic_account_id:
            raise UserError('Usted no puede eliminar la cuenta analítica, debe cancelar el pedido de venta.')
