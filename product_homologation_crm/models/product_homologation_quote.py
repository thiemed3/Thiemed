from odoo import fields, models


class ProductHomologationQuote(models.Model):
    _inherit = "product.homologation.quote"

    lead_id = fields.Many2one(
        "crm.lead",
        string="Oportunidad CRM",
        tracking=True,
        ondelete="set null",
    )
