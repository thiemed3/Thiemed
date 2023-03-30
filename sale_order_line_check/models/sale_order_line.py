from odoo import fields, models, api, _


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    check_imprimible = fields.Boolean(string='Producto imprimible', default=True, tracking=1)

    def _update_line_check_imprimible(self, values):
        orders = self.mapped('order_id')
        for order in orders:
            order_lines = self.filtered(lambda x: x.order_id == order)
            msg = "<b>" + _("El check de impresion ha sido modificado.") + "</b><ul>"
            for line in order_lines:
                if values['check_imprimible'] == False:
                    msg += "<li> %s: <br/>" % line.product_id.display_name
                    msg += _(
                        "Este producto no aparecera en la cotizacion"
                    )
                else:
                    msg += "<li> %s: <br/>" % line.product_id.display_name
                    msg += _(
                        "Este producto aparecera en la cotizacion"
                    )
                msg += "</ul>"
            order.message_post(body=msg)


    def write(self, values):
        res = super(SaleOrderLine, self).write(values)
        if 'check_imprimible' in values:
            self._update_line_check_imprimible(values)
        return res
