# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartnerMedicalLink(models.Model):
    _name = "res.partner.medical.link"
    _description = "Vínculo Médico - Institución"
    _order = "influence_level desc, id desc"

    doctor_id = fields.Many2one(
        "res.partner",
        string="Médico",
        required=True,
        index=True,
        domain=[("is_company", "=", False), ("is_doctor", "=", True)],
    )

    institution_id = fields.Many2one(
        "res.partner",
        string="Institución",
        required=True,
        index=True,
        domain=[("is_company", "=", True), ("is_institution", "=", True)],
    )

    job_position = fields.Char(string="Puesto de trabajo")
    influence_level = fields.Selection(
        [
            ("1", "Baja"),
            ("2", "Media"),
            ("3", "Alta"),
        ],
        string="Relevancia / Influencia",
        default="2",
        required=True,
    )
    institutional_email = fields.Char(string="Correo institucional")
    notes = fields.Text(string="Notas")
    active = fields.Boolean(default=True)

    # Campos “helper” (solo para mostrar info en la tabla)
    doctor_phone = fields.Char(related="doctor_id.phone", readonly=True)
    doctor_email = fields.Char(related="doctor_id.email", readonly=True)
    doctor_city = fields.Char(related="doctor_id.city", readonly=True)
    doctor_tags = fields.Many2many(related="doctor_id.category_id", readonly=True, string="Etiquetas")

    _sql_constraints = [
        ("uniq_doctor_institution", "unique(doctor_id, institution_id)",
         "Este vínculo Médico–Institución ya existe."),
    ]

    allowed_doctor_ids = fields.Many2many(
        "res.partner",
        compute="_compute_allowed_doctor_ids",
        string="Médicos disponibles",
        compute_sudo=True,
    )

    @api.depends("institution_id")
    def _compute_allowed_doctor_ids(self):
        Partner = self.env["res.partner"]
        for rec in self:
            if not rec.institution_id:
                rec.allowed_doctor_ids = Partner.browse()
                continue

            # Médicos ya asignados a esta institución
            assigned = self.search([("institution_id", "=", rec.institution_id.id)]).mapped("doctor_id").ids

            # Médicos disponibles (personas marcadas como médico) EXCLUYENDO los ya asignados
            rec.allowed_doctor_ids = Partner.search([
                ("is_company", "=", False),
                ("is_doctor", "=", True),
                ("id", "not in", assigned),
            ])

    @api.constrains("doctor_id", "institution_id")
    def _check_partner_types(self):
        for rec in self:
            if rec.doctor_id and rec.doctor_id.is_company:
                raise ValidationError("El campo 'Médico' debe ser una Persona (no compañía).")

            if rec.doctor_id and not rec.doctor_id.is_doctor:
                raise ValidationError("El contacto seleccionado no está marcado como 'Es médico'.")

            if rec.institution_id and not rec.institution_id.is_company:
                raise ValidationError("El campo 'Institución' debe ser una Compañía.")

            if rec.institution_id and not rec.institution_id.is_institution:
                raise ValidationError("La institución seleccionada no está marcada como 'Es institución'.")

            if rec.institution_id and not rec.institution_id.is_institution:
                raise ValidationError("La institución seleccionada no está marcada como 'Es institución'.")

    @api.onchange("doctor_id")
    def _onchange_doctor_id(self):
        if self.doctor_id and not self.doctor_id.is_doctor:
            self.doctor_id = False
            return {"warning": {"title": "Contacto no válido",
                                "message": "Solo puedes seleccionar contactos marcados como 'Es médico'."}}

    @api.onchange("institution_id")
    def _onchange_institution_id(self):
        if self.institution_id and not self.institution_id.is_institution:
            self.institution_id = False
            return {"warning": {"title": "Institución no válida",
                                "message": "Solo puedes seleccionar compañías marcadas como 'Es institución'."}}