# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartnerMedicalInfluence(models.Model):
    _name = "res.partner.medical.influence"
    _description = "Influencia (Vínculos médico institución)"
    _order = "name"

    name = fields.Char(string="Nombre", required=True, index=True)
    color = fields.Integer(string="Color")

    _uniq_name = models.Constraint(
        "unique(name)",
        "Ya existe una influencia con este nombre.",
    )
