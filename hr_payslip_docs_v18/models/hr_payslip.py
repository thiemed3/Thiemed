# -*- coding: utf-8 -*-
import base64
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    x_document_id = fields.Many2one(
        "documents.document", string="Documento", copy=False
    )
    x_doc_sent = fields.Boolean(
        string="Enviado a empleado", default=False, copy=False
    )

    # -------------------------------
    # Helpers de compatibilidad
    # -------------------------------
    def _documents_models(self):
        """Detecta cómo se llama el modelo de carpeta (si existe) y si existe documents.document."""
        env = self.env
        folder_model = None
        if "documents.folder" in env:
            folder_model = "documents.folder"
        elif "documents.workspace" in env:
            folder_model = "documents.workspace"

        document_model = "documents.document" if "documents.document" in env else None
        return folder_model, document_model

    def _get_or_create_payroll_folder(self, company):
        """
        Devuelve la carpeta 'Payroll' si hay modelo de carpetas; si no, devuelve None.
        Evita KeyError cuando no existe documents.folder/workspace.
        """
        folder_model, _ = self._documents_models()
        if not folder_model:
            return None

        Folder = self.env[folder_model].sudo()
        ICP = self.env["ir.config_parameter"].sudo()

        root_names = (ICP.get_param(
            "hr_payslip_docs.root_folder_names",
            default="Shared,Compartidos,Workspace,Documents,Documentos",
        ) or "").split(",")
        root_names = [n.strip() for n in root_names if n.strip()]

        payroll_name = ICP.get_param(
            "hr_payslip_docs.payroll_folder_name",
            default="Payroll",
        )

        # Buscar raíz en la compañía
        root = Folder.search([
            ("name", "in", root_names),
            ("parent_folder_id", "=", False),
            ("company_id", "=", company.id or False),
        ], limit=1)
        if not root:
            root = Folder.create({
                "name": (root_names[0] if root_names else "Documents"),
                "company_id": company.id or False,
            })

        # Buscar/crear carpeta Payroll
        payroll = Folder.search([
            ("name", "=", payroll_name),
            ("parent_folder_id", "=", root.id),
            ("company_id", "=", company.id or False),
        ], limit=1)
        if not payroll:
            payroll = Folder.create({
                "name": payroll_name,
                "parent_folder_id": root.id,
                "company_id": company.id or False,
            })
        return payroll

    def _render_payslip_pdf(self):
        """Renderiza el PDF del recibo usando el reporte de nómina (estándar o CL)."""
        self.ensure_one()
        report = (
            self.env.ref("hr_payroll.action_report_payslip", raise_if_not_found=False)
            or self.env.ref("l10n_cl_hr_payroll.action_report_payslip", raise_if_not_found=False)
        )
        if not report:
            raise UserError(_("No se encontró el reporte de nómina para generar el PDF."))
        pdf_content, _ = report._render_qweb_pdf(self.sudo().id)
        filename = "Payslip_%s.pdf" % (
            (self.number or self.name or ("slip_%s" % self.id)).replace("/", "_")
        )
        return filename, pdf_content

    def _generate_document_and_attachment(self, payroll_folder=None):
        """
        Siempre genera/actualiza el adjunto PDF del recibo.
        Si existen modelos de Documentos, también crea/actualiza documents.document.
        """
        self.ensure_one()
        slip = self.sudo()

        # 1) Render PDF
        filename, pdf_content = slip._render_payslip_pdf()

        # 2) Crear/actualizar adjunto
        Attachment = self.env["ir.attachment"].sudo()
        attachment = Attachment.search([
            ("res_model", "=", "hr.payslip"),
            ("res_id", "=", slip.id),
            ("name", "=", filename),
        ], limit=1)
        datas_b64 = base64.b64encode(pdf_content)
        if attachment:
            attachment.write({"datas": datas_b64})
        else:
            attachment = Attachment.create({
                "name": filename,
                "res_model": "hr.payslip",
                "res_id": slip.id,
                "type": "binary",
                "mimetype": "application/pdf",
                "datas": datas_b64,
            })

        # 3) Crear/actualizar documento (si existe documents.document)
        folder_model, document_model = self._documents_models()
        if document_model:
            Document = self.env[document_model].sudo()
            vals_doc = {
                "name": filename,
                "res_model": "hr.payslip",
                "res_id": slip.id,
                "attachment_id": attachment.id,
            }
            # Asignar folder solo si el campo existe y recibimos carpeta válida
            if payroll_folder and "folder_id" in Document._fields:
                vals_doc["folder_id"] = payroll_folder.id

            # Propietario: usuario del empleado si es interno
            if slip.employee_id.user_id and slip.employee_id.user_id.has_group("base.group_user"):
                vals_doc["owner_id"] = slip.employee_id.user_id.id

            doc = Document.search([
                ("res_model", "=", "hr.payslip"),
                ("res_id", "=", slip.id),
            ], limit=1)
            if doc:
                doc.write(vals_doc)
                slip.message_post(
                    body=_("Documento de nómina actualizado."),
                    attachment_ids=[attachment.id],
                )
            else:
                doc = Document.create(vals_doc)
                slip.message_post(
                    body=_("Documento de nómina creado."),
                    attachment_ids=[attachment.id],
                )
            slip.x_document_id = doc.id
        else:
            slip.message_post(
                body=_("PDF generado y adjuntado (app Documentos sin modelo de documentos disponible)."),
                attachment_ids=[attachment.id],
            )

        return attachment

    # -------------------------------
    # Email
    # -------------------------------
    def _get_employee_email(self):
        self.ensure_one()
        return self.employee_id.work_email or self.employee_id.private_email or ""

    def _send_email(self):
        """Envía el email al empleado usando la plantilla.
        La plantilla adjunta el PDF automáticamente vía report_template_ids."""
        self.ensure_one()
        slip = self.sudo()

        email = slip._get_employee_email()
        if not email:
            slip.message_post(body=_("No se envió correo: el empleado no tiene email."))
            return False

        template = self.env.ref(
            "hr_payslip_docs_v18.mail_template_payslip_to_employee",
            raise_if_not_found=False,
        )
        if not template:
            slip.message_post(body=_("No se encontró la plantilla de correo."))
            return False

        try:
            # La plantilla tiene email_to evaluado con object, por lo que no pasamos email_values
            template.send_mail(
                slip.id,
                force_send=True,
                raise_exception=False,
            )
            slip.message_post(body=_("Recibo enviado a: %s") % email)
            return True
        except Exception as exc:  # pylint: disable=broad-except
            slip.message_post(body=_("Error al enviar correo: %s") % exc)
            return False

    # -------------------------------
    # Acción masiva / Cron
    # -------------------------------
    def _group_by_company(self):
        """Agrupa los slips por compañía."""
        res = {}
        for slip in self:
            key = slip.company_id
            res.setdefault(key, self.env["hr.payslip"])
            res[key] |= slip
        return res

    def action_generate_document_and_send_email(self):
        """Acción masiva: genera documento/adjunto y envía correo."""
        for company, slips in self._group_by_company().items():
            payroll_folder = self._get_or_create_payroll_folder(company)
            for slip in slips:
                try:
                    slip._generate_document_and_attachment(payroll_folder)
                    if slip._send_email():
                        slip.x_doc_sent = True
                except Exception as exc:  # pylint: disable=broad-except
                    slip.message_post(body=_("Error procesando recibo: %s") % exc)
        return True
