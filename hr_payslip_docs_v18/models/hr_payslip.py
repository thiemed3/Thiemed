# -*- coding: utf-8 -*-
import base64
from collections import defaultdict
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    # Relación al documento en la app Documentos
    x_document_id = fields.Many2one(
        "documents.document",
        string="Documento de nómina",
        ondelete="set null",
        copy=False,
        readonly=True,
        help="PDF generado y archivado en Documentos vinculado a este recibo.",
    )

    # (opcional, pero lo usas en el código)
    x_doc_sent = fields.Boolean(
        string="Documento enviado",
        default=False,
        copy=False,
        help="Marcado cuando se generó el PDF y se envió por correo.",
    )

    # -------------------------------------
    # Helpers de Configuración y Carpetas
    # -------------------------------------
    def _get_config_param(self, param_name, default_value):
        return self.env["ir.config_parameter"].sudo().get_param(param_name, default_value)

    def _get_root_folder_names(self):
        names_str = self._get_config_param(
            "hr_payslip_docs.root_folder_names",
            "Shared,Compartidos,Workspace,Documents,Documentos",
        )
        return [name.strip() for name in names_str.split(",")]

    def _get_payroll_folder_name(self):
        return self._get_config_param("hr_payslip_docs.payroll_folder_name", "Payroll")

    def _get_internal_owner_for_employee(self, payslip):
        user = payslip.employee_id.user_id
        if user and self.env.ref("base.group_user") in user.groups_id:
            return user
        return False

    def _get_or_create_payroll_folder(self, company):
        Folder = self.env["documents.folder"]
        group_user = self.env.ref("base.group_user")
        payroll_folder_name = self._get_payroll_folder_name()

        root_name_candidates = self._get_root_folder_names()
        root = Folder.search([
            ("parent_folder_id", "=", False),
            ("company_id", "in", [company.id, False]),
            ("name", "in", root_name_candidates),
        ], order="company_id desc, id asc", limit=1)

        if not root:
            root = Folder.search([
                ("parent_folder_id", "=", False),
                ("company_id", "in", [company.id, False]),
            ], order="company_id desc, id asc", limit=1)
            if not root:
                root = Folder.create({
                    "name": root_name_candidates[0],
                    "company_id": company.id,
                    "group_ids": [(4, group_user.id)],
                })

        payroll_folder = Folder.search([
            ("name", "=", payroll_folder_name),
            ("company_id", "in", [company.id, False]),
            ("parent_folder_id", "=", root.id),
        ], limit=1)

        if not payroll_folder:
            payroll_folder = Folder.create({
                "name": payroll_folder_name,
                "company_id": company.id,
                "parent_folder_id": root.id,
                "group_ids": [(4, group_user.id)],
            })
        return payroll_folder

    # ------------------------------------
    # Core: Generar PDF + Documento
    # ------------------------------------
    def _generate_document_and_attachment(self, payroll_folder):
    """Genera el PDF del recibo, crea/actualiza el adjunto y el documento."""
    self.ensure_one()

    # 1) Buscar el reporte con fallback a localización CL
    report = (
        self.env.ref("hr_payroll.action_report_payslip", raise_if_not_found=False)
        or self.env.ref("l10n_cl_hr_payroll.action_report_payslip", raise_if_not_found=False)
    )
    if not report:
        raise UserError(_("No se encontró el reporte de nómina (hr_payroll/l10n_cl_hr_payroll)."))

    # 2) Renderizar PDF (sudo por si el usuario no puede imprimir reportes)
    pdf_content, _ = report.sudo()._render_qweb_pdf(self.id)
    if not pdf_content:
        raise UserError(_("No fue posible generar el PDF del recibo."))

    # 3) Nombre de archivo estable e idempotente
    slip_code = self.number or self.name or f"slip_{self.id}"
    filename = f"Payslip_{slip_code.replace('/', '_')}.pdf"

    # 4) Crear/actualizar adjunto binario (sudo para evitar AccessError)
    Attachment = self.env["ir.attachment"].sudo()
    attachment = Attachment.search([
        ("res_model", "=", "hr.payslip"),
        ("res_id", "=", self.id),
        ("name", "=", filename),
        ("mimetype", "=", "application/pdf"),
    ], limit=1)

    vals_att = {
        "name": filename,
        "res_model": "hr.payslip",
        "res_id": self.id,
        "type": "binary",
        "mimetype": "application/pdf",
        "datas": base64.b64encode(pdf_content),
    }
    if attachment:
        attachment.write(vals_att)
    else:
        attachment = Attachment.create(vals_att)

    # 5) Asegurar documento en la carpeta de Documentos (sudo y checks)
    if not self.env.registry.get("documents.document"):
        raise UserError(_(
            "No se encontró el modelo 'documents.document' en el registro actual. "
            "Reinicia el servidor si acabas de instalar 'Documents'."
        ))

    owner_user = self._get_internal_owner_for_employee(self) or self.env.user
    Document = self.env["documents.document"].sudo()

    # Intento 1: por attachment
    document = Document.search([("attachment_id", "=", attachment.id)], limit=1)
    # Intento 2: por vínculo al recurso + nombre (idempotencia)
    if not document:
        document = Document.search([
            ("res_model", "=", "hr.payslip"),
            ("res_id", "=", self.id),
            ("name", "=", filename),
        ], limit=1)

    vals_doc = {
        "folder_id": payroll_folder.sudo().id,
        "owner_id": owner_user.id,
        "name": filename,
        "partner_id": (self.employee_id.address_home_id.id if self.employee_id.address_home_id else False),
        "res_model": "hr.payslip",
        "res_id": self.id,
        "company_id": self.company_id.id if self.company_id else False,
        "attachment_id": attachment.id,
    }
    if document:
        document.write(vals_doc)
    else:
        document = Document.create(vals_doc)

    # 6) Enlazar en la nómina y mensajería
    self.x_document_id = document.id

    if not self._get_internal_owner_for_employee(self):
        self.message_post(
            body=_(
                "⚠️ El empleado <b>%s</b> no tiene usuario interno. "
                "El PDF se guardó en Documentos, pero el empleado no podrá verlo "
                "hasta que tenga un usuario interno asignado."
            ) % (self.employee_id.name,),
            message_type="comment",
        )

    self.message_post(
        body=_("📄 Documento generado/actualizado en Documentos: %s") % filename,
        message_type="notification",
        attachment_ids=[attachment.id],
    )


    # -----------------------------
    # Envío de Correo
    # -----------------------------
    def _get_employee_email(self):
        self.ensure_one()
        return self.employee_id.work_email or self.employee_id.private_email

    def _send_email(self):
        self.ensure_one()
        email_to = self._get_employee_email()
        if not email_to:
            raise UserError(
                _("El empleado %s no tiene correo configurado (laboral o privado).") % self.employee_id.name)

        # FIX: id correcto
        template = self.env.ref("hr_payslip_docs_v18.mail_template_payslip_to_employee")
        lang = self.employee_id.user_id.lang or self.env.user.lang
        template.with_context(lang=lang).send_mail(
            self.id,
            force_send=True,
            email_values={"email_to": email_to},
        )
        self.message_post(body=_("✉️ Recibo enviado a: %s") % email_to, message_type="comment")

    # ----------------------------------------------
    # Acción pública
    # ----------------------------------------------
    def action_generate_document_and_send_email(self):
        if any(slip.state != "done" for slip in self):
            raise UserError(_("Todas las nóminas deben estar en estado 'Hecho'."))

        slips_by_company = defaultdict(lambda: self.env["hr.payslip"])
        for slip in self:
            slips_by_company[slip.company_id] |= slip

        for company, slips in slips_by_company.items():
            payroll_folder = self._get_or_create_payroll_folder(company)
            for slip in slips:
                try:
                    slip._generate_document_and_attachment(payroll_folder)
                    slip._send_email()
                    slip.x_doc_sent = True
                except UserError as e:
                    slip.message_post(body=_("Error al procesar: %s") % e)
                except Exception as e:
                    slip.message_post(body=_("Error inesperado: %s") % e)
        return True
