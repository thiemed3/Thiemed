from odoo import fields, models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    sale_order_id = fields.Many2one('sale.order', string='Pedido', compute='_compute_sale_order_id', store=True)

    # def buscar_pedido(self):
    #     for rec in self:
    #         if rec.invoice_origin:
    #             sale_order = self.env['sale.order'].search([('name', '=', rec.invoice_origin)])
    #             return sale_order

    @api.depends('invoice_origin')
    def _compute_sale_order_id(self):
        for rec in self:
            sale_order = self.env['sale.order'].search([('name', '=', rec.invoice_origin)])
            if sale_order:
                rec.sale_order_id = sale_order.id
            else:
                rec.sale_order_id = False

