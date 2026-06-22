from odoo import fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    homologation_quote_ids = fields.One2many(
        "product.homologation.quote",
        "lead_id",
        string="Precotizaciones",
    )
    homologation_quote_count = fields.Integer(
        string="Precotizaciones",
        compute="_compute_homologation_quote_count",
    )

    def _compute_homologation_quote_count(self):
        for lead in self:
            lead.homologation_quote_count = self.env[
                "product.homologation.quote"
            ].search_count([("lead_id", "=", lead.id)])

    def action_open_homologation_quotes(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Precotizaciones",
            "res_model": "product.homologation.quote",
            "domain": [("lead_id", "=", self.id)],
            "context": {
                "default_lead_id": self.id,
                "default_partner_id": self.partner_id.id,
            },
            "view_mode": "list,form",
        }
