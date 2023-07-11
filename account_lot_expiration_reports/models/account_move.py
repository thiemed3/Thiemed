from odoo import fields, models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    sale_order_id = fields.Many2one('sale.order', string='Pedido', compute='_compute_sale_order_id', store=True)
    # cantidad_lote = fields.Char(string='Cantidad Lote', compute='_compute_cantidad_lote')

    @api.depends('invoice_origin')
    def _compute_sale_order_id(self):
        for rec in self:
            sale_order = self.env['sale.order'].search([('name', '=', rec.invoice_origin)])
            if sale_order:
                rec.sale_order_id = sale_order.id
            else:
                rec.sale_order_id = False


    # AGREGAR EL ID DE LA FACTURA EN LA GUIA DE DESPACHO AL CONFIRMAR LA FACTURA
    def action_post(self):
        res = super(AccountMove, self).action_post()
        for rec in self:
            for lines in rec.invoice_line_ids:
                movimientos = lines.sale_line_ids.move_ids.mapped('move_line_ids')
                for stock_line in movimientos:
                    if stock_line.state == 'done':
                        if stock_line.is_factured == False:
                            stock_line.write({'is_factured': True})










