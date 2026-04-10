# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError, RedirectWarning


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_doctor = fields.Boolean(string="Es médico")
    is_institution = fields.Boolean(string="Es institución")

    institution_link_ids = fields.One2many(
        "res.partner.medical.link",
        "doctor_id",
        string="Instituciones",
    )

    doctor_link_ids = fields.One2many(
        "res.partner.medical.link",
        "institution_id",
        string="Médicos",
    )


    institution_ids = fields.Many2many(
        comodel_name="res.partner",
        string="Instituciones",
        compute="_compute_institution_ids",
        search="_search_institution_ids",
        compute_sudo=True,
    )

    @api.depends("institution_link_ids.institution_id")
    def _compute_institution_ids(self):
        for partner in self:
            partner.institution_ids = partner.institution_link_ids.mapped("institution_id")

    def _search_institution_ids(self, operator, value):
        """Permite que la barra de búsqueda filtre doctores por nombre/id de institución."""
        Partner = self.env["res.partner"].sudo()

        # Caso texto: "Buscar Instituciones para: clinica"
        if operator in ("ilike", "like", "=ilike", "=like"):
            insts = Partner.search([
                ("is_company", "=", True),
                ("is_institution", "=", True),
                ("name", operator, value),
            ])
            return [("institution_link_ids.institution_id", "in", insts.ids)]

        # Caso selección por IDs (cuando eliges institución desde widget)
        if operator in ("=", "in"):
            ids = value if isinstance(value, (list, tuple)) else [value]
            return [("institution_link_ids.institution_id", "in", ids)]

        # Negaciones
        if operator in ("!=", "not in"):
            ids = value if isinstance(value, (list, tuple)) else [value]
            return ["|",
                    ("institution_link_ids", "=", False),
                    ("institution_link_ids.institution_id", "not in", ids)]

        if operator in ("not ilike", "not like"):
            insts = Partner.search([
                ("is_company", "=", True),
                ("is_institution", "=", True),
                ("name", "ilike", value),
            ])
            return ["|",
                    ("institution_link_ids", "=", False),
                    ("institution_link_ids.institution_id", "not in", insts.ids)]

        return []

    # -------------------------
    # UX: avisos inmediatos
    # -------------------------
    @api.onchange("is_doctor", "company_type")
    def _onchange_is_doctor_company_type(self):
        if self.is_doctor and self.company_type != "person":
            self.is_doctor = False
            return {
                "warning": {
                    "title": "No permitido",
                    "message": "Un contacto marcado como 'Es médico' debe ser Persona.",
                }
            }

    @api.onchange("is_institution", "company_type")
    def _onchange_is_institution_company_type(self):
        if self.is_institution and self.company_type != "company":
            self.is_institution = False
            return {
                "warning": {
                    "title": "No permitido",
                    "message": "Un contacto marcado como 'Es institución' debe ser Compañía.",
                }
            }

    @api.onchange("company_type")
    def _onchange_company_type_block_by_roles(self):
        # Solo advertir/revertir en UI (el candado real está en write/constrains)
        if not self._origin:
            return
        old = self._origin.company_type

        if self.company_type == "person" and self.is_institution:
            self.company_type = old
            return {
                "warning": {
                    "title": "No permitido",
                    "message": "No puedes cambiar a Persona si 'Es institución' está activo.",
                }
            }

        if self.company_type == "company" and self.is_doctor:
            self.company_type = old
            return {
                "warning": {
                    "title": "No permitido",
                    "message": "No puedes cambiar a Compañía si 'Es médico' está activo.",
                }
            }

    # -------------------------
    # Candado real (DB)
    # -------------------------
    @api.constrains("company_type", "is_doctor", "is_institution")
    def _check_roles_vs_company_type(self):
        for p in self:
            if p.is_doctor and p.company_type != "person":
                raise ValidationError("Si 'Es médico' está activo, el contacto debe ser Persona.")
            if p.is_institution and p.company_type != "company":
                raise ValidationError("Si 'Es institución' está activo, el contacto debe ser Compañía.")
            if p.is_doctor and p.is_institution:
                raise ValidationError("Un contacto no puede ser 'médico' e 'institución' al mismo tiempo.")

    def write(self, vals):
        Action = self.env.ref("ints_medics_module.action_partner_role_deactivate_wizard", raise_if_not_found=False)

        for p in self:
            # valores futuros (para validar combinaciones en un mismo write)
            future_company_type = vals.get("company_type", p.company_type)
            future_is_doctor = vals.get("is_doctor", p.is_doctor)
            future_is_institution = vals.get("is_institution", p.is_institution)

            # Bloqueos por tipo según rol
            if future_is_institution and future_company_type != "company":
                raise ValidationError("No puedes dejar 'Es institución' activo si el contacto es Persona.")
            if future_is_doctor and future_company_type != "person":
                raise ValidationError("No puedes dejar 'Es médico' activo si el contacto es Compañía.")
            if future_is_doctor and future_is_institution:
                raise ValidationError("Un contacto no puede ser 'médico' e 'institución' a la vez.")

            # Si intentan DESACTIVAR rol con vínculos existentes -> ofrecer limpiar/cancelar
            if Action:
                if "is_doctor" in vals and not vals["is_doctor"] and p.institution_link_ids:
                    ctx = {"default_partner_id": p.id, "default_role": "doctor"}
                    raise RedirectWarning(
                        "Este médico tiene instituciones vinculadas. ¿Quieres limpiar los vínculos y desactivar el rol?",
                        Action.id,
                        "Limpiar vínculos",
                        ctx,
                    )

                if "is_institution" in vals and not vals["is_institution"] and p.doctor_link_ids:
                    ctx = {"default_partner_id": p.id, "default_role": "institution"}
                    raise RedirectWarning(
                        "Esta institución tiene médicos vinculados. ¿Quieres limpiar los vínculos y desactivar el rol?",
                        Action.id,
                        "Limpiar vínculos",
                        ctx,
                    )

        return super().write(vals)