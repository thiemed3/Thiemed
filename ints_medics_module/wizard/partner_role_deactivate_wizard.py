# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PartnerRoleDeactivateWizard(models.TransientModel):
    _name = "partner.role.deactivate.wizard"
    _description = "Desactivar rol Médico/Institución (limpiar vínculos)"

    partner_id = fields.Many2one("res.partner", required=True, readonly=True)
    role = fields.Selection(
        [("doctor", "Médico"), ("institution", "Institución")],
        required=True,
        readonly=True,
    )
    links_count = fields.Integer(compute="_compute_links_count", readonly=True)

    @api.depends("partner_id", "role")
    def _compute_links_count(self):
        Link = self.env["res.partner.medical.link"]
        for w in self:
            if not w.partner_id:
                w.links_count = 0
                continue
            if w.role == "doctor":
                w.links_count = Link.search_count([("doctor_id", "=", w.partner_id.id)])
            else:
                w.links_count = Link.search_count([("institution_id", "=", w.partner_id.id)])

    def action_clean_and_deactivate(self):
        self.ensure_one()
        Link = self.env["res.partner.medical.link"]

        if self.role == "doctor":
            Link.search([("doctor_id", "=", self.partner_id.id)]).unlink()
            self.partner_id.write({"is_doctor": False})
        else:
            Link.search([("institution_id", "=", self.partner_id.id)]).unlink()
            self.partner_id.write({"is_institution": False})

        return {"type": "ir.actions.act_window_close"}