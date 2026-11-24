from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    homologation_lead_id = fields.Many2one(
        "crm.lead",
        string="Oportunidad de homologación",
        readonly=True,
        index=True,
        ondelete="set null",
        help="Oportunidad CRM vinculada a la precotización de origen.",
    )
