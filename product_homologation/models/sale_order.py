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
    homologation_observation = fields.Text(
        string="Observación de homologación",
        help="Observación registrada en la homologación validada al convertir.",
    )
    homologation_quote_observation = fields.Text(
        string="Observación de precotización",
        help="Observación propia de la línea de precotización al convertir.",
    )
    homologation_level = fields.Selection(
        [
            ("exact", "Coincidencia exacta"),
            ("near", "Coincidencia cercana"),
            ("approximate", "Coincidencia aproximada"),
            ("best", "Mejor opción"),
        ],
        string="Nivel de homologación",
    )
    homologation_precision_pct = fields.Float(string="Precisión homologación (%)")
    homologation_quote_line_id = fields.Many2one(
        "product.homologation.quote.line",
        string="Línea de precotización",
        ondelete="set null",
    )
