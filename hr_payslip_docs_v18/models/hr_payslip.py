# -*- coding: utf-8 -*-
import base64
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    # En tu base existe documents.document; si en otra base no existiera,
    # este campo requeriría que el módulo 'documents' esté instalado.
    x_document_id = fields.Many2one(
        "documents.document",
        string="Documento",
        copy=False,
    )
    x_doc_sent = fields.Boolean(
        string="Enviado a empleado",
        default=False,
        copy=False,
    )

    # -------------------------------------------------------------------------
    # Helpers: Documentos (compatibilidad con diferentes nombres de modelo/campos)
    # -------------------------------------------------------------------------
    def _documents_models(self):
        """
        Detecta los nombres de modelos disponibles de Documentos.
        Devuelve (folder_model, document_model).
        folder_model puede ser 'documents.folder', 'documents.workspace' o None.
        document_model es 'documents.document' o None.
        """
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
        Devuelve una carpeta/workspace 'Payroll' si el modelo de carpetas existe.
        Si no existe modelo de carpeta, devuelve None (y el flujo no falla).
        Maneja diferencias de nombres de campos entre implementations.
        """
        folder_model, _ = self._documents_models()
        if not folder_model:
            return None

        Folder = self.env[folder_model].sudo()

        # Campos potencialmente distintos según el modelo
        parent_field = "parent_folder_id" if "parent_folder_id" in Folder._fields else (
            "parent_id" if "parent_id" in Folder._fields else None
        )
        company_field = "company_id" if "company_id" in Folder._fields else None

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

        # --- Buscar/crear raíz ---
        domain_root = [("name", "in", root_names)]
        if parent_field:
            domain_root.append((parent_field, "=", False))
        if company_field:
            domain_root.append((company_field, "=", company.id or False))

        root = Folder.search(domain_root, limit=1)
        if not root:
            vals_root = {"name": (root_names[0] if root_names else "Documents")}
            if company_field:
                vals_root[company_field] = company.id or False
            root = Folder.create(vals_root)

        # --- Buscar/crear 'Payroll' debajo de la raíz ---
        domain_payroll = [("name", "=", payroll_name)]
        if parent_field:
            domain_payroll.append((parent_field, "=", root.id))
        if company_field:
            domain_payroll.append((company_field, "=", company.id or False))

        payroll = Folder.search(domain_payroll, limit=1)
        if not payroll:
            vals_payroll = {"name": payroll_name}
            if parent_field:
                vals_payroll[parent_field] = root.id
            if company_field:
                vals_payroll[company_field] = company.id or False
            payroll = Folder.create(vals_payroll)
        return payroll

    # -------------------------------------------------------------------------
    # Reporte de nómina (robusto)
    # -------------------------------------------------------------------------
    def _get_payslip_report(self):
        """
        Devuelve un ir.actions.report válido para hr.payslip.
        Intenta por XML-ID estándar, luego por búsqueda del modelo.
        """
        self.ensure_one()
        Report = self.env["ir.actions.report"].sudo()

        # 1) Por XML-ID (estándar y CL)
        for xmlid in (
            "hr_payroll.action_report_payslip",
            "l10n_cl_hr_payroll.action_report_payslip",
        ):
            rep = self.env.ref(xmlid, raise_if_not_found=False)
            if rep and rep.exists():
                return rep.sudo()

        # 2) Fallback: cualquier QWeb de hr.payslip
        rep = Report.search(
            [("model", "=", "hr.payslip"), ("report_type", "in", ["qweb-pdf", "qweb"])],
            limit=1,
        )
        if rep:
            return rep

        # 3) Nada encontrado
        raise UserError(_(
            "No se encontró ninguna acción de reporte para Recibo de nómina. "
            "Actualiza 'hr_payroll' (y/o 'l10n_cl_hr_payroll') o crea un reporte QWeb para 'hr.payslip'."
        ))

    def _render_payslip_pdf(self):
        """Renderiza el PDF del recibo y devuelve (filename, pdf_bytes)."""
        self.ensure_one()
        report = self._get_payslip_report()
        pdf_content, _ = report._render_qweb_pdf(self.sudo().id)
        filename = "Payslip_%s.pdf" % (
            (self.number or self.name or ("slip_%s" % self.id)).replace("/", "_")
        )
        return filename, pdf_content

    # -------------------------------------------------------------------------
    # Generación de adjunto + documento
    # -------------------------------------------------------------------------
    def _expected_filename(self):
        """Nombre de archivo esperado para el adjunto/documento."""
        self.ensure_one()
        return "Payslip_%s.pdf" % (
            (self.number or self.name or ("slip_%s" % self.id)).replace("/", "_")
        )

    def _find_payslip_attachment(self):
        """Busca el adjunto esperado del recibo."""
        self.ensure_one()
        Attachment = self.env["ir.attachment"].sudo()
        return Attachment.search(
            [
                ("res_model", "=", "hr.payslip"),
                ("res_id", "=", self.id),
                ("name", "=", self._expected_filename()),
            ],
            limit=1,
        )

    def _generate_document_and_attachment(self, payroll_folder=None):
        """
        Siempre genera/actualiza el adjunto PDF del recibo.
        Si existen modelos de Documentos, también crea/actualiza el documents.document.
        """
        self.ensure_one()
        slip = self.sudo()

        # 1) Render PDF
        filename, pdf_content = slip._render_payslip_pdf()

        # 2) Crear/actualizar adjunto
        Attachment = self.env["ir.attachment"].sudo()
        attachment = Attachment.search(
            [
                ("res_model", "=", "hr.payslip"),
                ("res_id", "=", slip.id),
                ("name", "=", filename),
            ],
            limit=1,
        )
        datas_b64 = base64.b64encode(pdf_content)
        if attachment:
            attachment.write({"datas": datas_b64})
        else:
            attachment = Attachment.create(
                {
                    "name": filename,
                    "res_model": "hr.payslip",
                    "res_id": slip.id,
                    "type": "binary",
                    "mimetype": "application/pdf",
                    "datas": datas_b64,
                }
            )

        # 3) Crear/actualizar documento en Documentos (si existe el modelo)
        folder_model, document_model = self._documents_models()
        if document_model:
            Document = self.env[document_model].sudo()

            # Campo de carpeta puede llamarse 'folder_id' o 'workspace_id'
            folder_field = None
            for candidate in ("folder_id", "workspace_id"):
                if candidate in Document._fields:
                    folder_field = candidate
                    break

            vals_doc = {
                "name": filename,
                "res_model": "hr.payslip",
                "res_id": slip.id,
                "attachment_id": attachment.id,
            }
            if payroll_folder and folder_field:
                vals_doc[folder_field] = payroll_folder.id

            # Propietario: usuario interno del empleado (si corresponde)
            if (
                slip.employee_id.user_id
                and slip.employee_id.user_id.has_group("base.group_user")
                and "owner_id" in Document._fields
            ):
                vals_doc["owner_id"] = slip.employee_id.user_id.id

            doc = Document.search(
                [("res_model", "=", "hr.payslip"), ("res_id", "=", slip.id)],
                limit=1,
            )
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
                body=_("PDF generado y adjuntado (app Documentos no disponible o sin modelo de documento)."),
                attachment_ids=[attachment.id],
            )

        return attachment

    # -------------------------------------------------------------------------
    # Email
    # -------------------------------------------------------------------------
    def _get_employee_email(self):
        """Devuelve el correo del empleado (laboral o privado) o cadena vacía."""
        self.ensure_one()
        return self.employee_id.work_email or self.employee_id.private_email or ""

    def _send_email(self, attachment=None):
        """
        Envía el email al empleado usando la plantilla del módulo.
        - Si se pasa `attachment`, se adjunta explícitamente (independiente de la plantilla).
        - Registra el resultado en el chatter y devuelve True/False.
        """
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
            email_values = {}
            if attachment:
                email_values["attachment_ids"] = [(4, attachment.id)]

            template.send_mail(
                slip.id,
                force_send=True,
                raise_exception=False,
                email_values=email_values,
            )
            slip.message_post(body=_("Recibo enviado a: %s") % email)
            return True
        except Exception as exc:  # pylint: disable=broad-except
            slip.message_post(body=_("Error al enviar correo: %s") % exc)
            return False

    # -------------------------------------------------------------------------
    # Agrupación por compañía
    # -------------------------------------------------------------------------
    def _group_by_company(self):
        """Agrupa los slips por compañía para crear carpetas en su contexto."""
        res = {}
        for slip in self:
            key = slip.company_id
            res.setdefault(key, self.env["hr.payslip"])
            res[key] |= slip
        return res

    # -------------------------------------------------------------------------
    # Acciones públicas
    # -------------------------------------------------------------------------
    def action_generate_payslip_document(self):
        """
        SOLO GENERAR: crea/actualiza el PDF y el documento (si aplica), sin enviar correo.
        Ideal para revisión previa.
        """
        for company, slips in self._group_by_company().items():
            folder = self._get_or_create_payroll_folder(company)
            for slip in slips:
                try:
                    slip._generate_document_and_attachment(folder)
                except Exception as exc:  # pylint: disable=broad-except
                    slip.sudo().message_post(body=_("Error generando documento: %s") % exc)
        return True

    def action_send_payslip_email_only(self):
        """
        SOLO ENVIAR: envía correo si ya existe el PDF.
        Si no existe, avisa en el chatter y no envía.
        """
        for slip in self.sudo():
            try:
                att = slip._find_payslip_attachment()
                if not att:
                    slip.message_post(
                        body=_(
                            "No se envió correo: el PDF aún no está generado. "
                            "Ejecuta primero 'Generar documento'."
                        )
                    )
                    continue
                if slip._send_email(attachment=att):
                    slip.x_doc_sent = True
            except Exception as exc:  # pylint: disable=broad-except
                slip.message_post(body=_("Error enviando correo: %s") % exc)
        return True

    def action_generate_document_and_send_email(self):
        """
        GENERAR + ENVIAR: flujo completo.
        Idempotente: actualiza adjunto/documento y reenvía si procede.
        """
        for company, slips in self._group_by_company().items():
            payroll_folder = self._get_or_create_payroll_folder(company)
            for slip in slips:
                try:
                    att = slip._generate_document_and_attachment(payroll_folder)
                    if slip._send_email(attachment=att):
                        slip.x_doc_sent = True
                except Exception as exc:  # pylint: disable=broad-except
                    slip.message_post(body=_("Error procesando recibo: %s") % exc)
        return True
