from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    homologation_customer_code = fields.Char(
        string="Código original del cliente",
        help="Código del producto según el listado del cliente, conservado para trazabilidad.",
    )
    homologation_customer_description = fields.Text(
        string="Descripción original del cliente",
        help="Descripción original del producto, conservada para trazabilidad.",
    )
    homologation_quote_line_id = fields.Many2one(
        "product.homologation.quote.line",
        string="Línea de precotización",
        ondelete="set null",
    )
