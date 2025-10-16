# -*- coding: utf-8 -*-
import base64
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    x_doc_sent = fields.Boolean(
        string="Documento de nómina enviado",
        default=False,
        help="Marcado cuando se generó el documento y se intentó el envío de email.",
        tracking=True,
    )
    
    x_document_id = fields.Many2one(
        'documents.document',
        string="Documento en Documentos",
        readonly=True,
        help="Vínculo al documento PDF en la aplicación Documentos"
    )

    def _get_payslip_filename(self):
        """Nombre consistente para el PDF/adjunto/documento."""
        self.ensure_one()
        base = (self.number or self.name or "SIN_NUMERO").replace("/", "_")
        return f"Recibo_{base}.pdf"
    
    def _get_or_create_payslip_folder(self):
        """
        Obtiene o crea la carpeta 'Nóminas' en Documents.
        Retorna: documents.folder record
        """
        Folder = self.env['documents.folder']
        folder = Folder.search([
            ('name', '=', 'Nóminas'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        
        if not folder:
            folder = Folder.create({
                'name': 'Nóminas',
                'company_id': self.company_id.id,
                'description': 'Recibos de nómina de empleados',
            })
            _logger.info("Carpeta 'Nóminas' creada en Documents para empresa %s", self.company_id.name)
        
        return folder

    def _generate_document_and_attachment(self):
        """
        Genera (si no existe) el PDF de la nómina, lo adjunta a la payslip
        y crea el registro en Documents. Retorna documents.document.
        
        CAMBIOS ODOO 18:
        - Eliminado 'datas_fname' (obsoleto)
        - Uso correcto de _render_qweb_pdf()
        - Folder específico en Documents
        - Vinculación bidireccional con x_document_id
        """
        self.ensure_one()
        
        if not self.employee_id:
            raise UserError(_("La nómina debe tener un empleado asociado."))
        
        payslip = self
        filename = payslip._get_payslip_filename()

        # 0) Buscar attachment existente (idempotencia)
        Attachment = self.env["ir.attachment"]
        att = Attachment.search([
            ("res_model", "=", "hr.payslip"),
            ("res_id", "=", payslip.id),
            ("name", "=", filename),
            ("mimetype", "=", "application/pdf"),
        ], limit=1)

        if not att:
            # 1) Render PDF QWeb (API Odoo 18)
            report = self.env.ref("hr_payroll.action_report_payslip")
            
            try:
                # _render_qweb_pdf para reportes QWeb
                # Retorna (pdf_content, format) donde format es 'pdf'
                pdf_content, _ = report._render_qweb_pdf(res_ids=[payslip.id])
            except Exception as e:
                _logger.error("Error generando PDF QWeb para nómina %s: %s", payslip.name, e)
                raise UserError(_("No se pudo generar el PDF de la nómina. Error: %s") % str(e))

            # 2) Crear attachment enlazado a hr.payslip
            # CORRECCIÓN: 'datas_fname' eliminado (obsoleto en v18)
            att = Attachment.create({
                "name": filename,
                "type": "binary",
                "mimetype": "application/pdf",
                "datas": base64.b64encode(pdf_content),
                "res_model": "hr.payslip",
                "res_id": payslip.id,
                "description": f"Recibo de nómina {payslip.name}",
            })
            _logger.info("Attachment creado: %s (ID: %s)", filename, att.id)

        # 3) Crear/obtener Documents (idempotente)
        Document = self.env["documents.document"]
        doc = Document.search([("attachment_id", "=", att.id)], limit=1)
        
        if not doc:
            # Obtener o crear carpeta específica
            folder = self._get_or_create_payslip_folder()
            
            # Owner: usuario del empleado o el usuario actual
            owner_user = payslip.employee_id.user_id or self.env.user
            
            doc_vals = {
                "name": filename,
                "attachment_id": att.id,
                "folder_id": folder.id,
                "owner_id": owner_user.id,
                "partner_id": payslip.employee_id.address_home_id.id if payslip.employee_id.address_home_id else False,
                "res_model": "hr.payslip",
                "res_id": payslip.id,
                "company_id": payslip.company_id.id,
            }
            doc = Document.create(doc_vals)
            
            # Vincular el documento a la nómina
            payslip.x_document_id = doc.id
            
            _logger.info("Documento creado en Documents: %s (ID: %s)", filename, doc.id)

        return doc

    def _send_email(self):
        """
        Envía el correo con plantilla; maneja idioma y ausencia de email.
        
        CAMBIOS ODOO 18:
        - message_post_with_template() reemplazado por send_mail()
        - Mejor manejo de errores
        - Validación de email del empleado
        """
        self.ensure_one()
        
        # Validar que el empleado tenga email
        employee_email = self.employee_id.work_email or (
            self.employee_id.address_home_id and self.employee_id.address_home_id.email
        )
        
        if not employee_email:
            _logger.warning(
                "Nómina %s: El empleado %s no tiene email configurado. No se envió correo.",
                self.name, self.employee_id.name
            )
            return False
        
        try:
            template = self.env.ref('hr_payslip_docs.email_template_payslip')
            lang = self.employee_id.address_home_id.lang or self.env.user.lang or 'es_CL'
            
            # CORRECCIÓN: En Odoo 18, usar send_mail() directamente
            template.with_context(lang=lang).send_mail(
                self.id,
                force_send=True,
                email_values={
                    'email_to': employee_email,
                }
            )
            
            _logger.info("Correo enviado exitosamente para nómina %s a %s", self.name, employee_email)
            return True
            
        except Exception as e:
            _logger.error("No se pudo enviar correo para la nómina %s: %s", self.name, e)
            return False

    def action_generate_document_and_send_email(self):
        """
        Acción general: genera documento y envía email (con idempotencia y bandera).
        Usada por la automatización.
        """
        for payslip in self:
            if payslip.x_doc_sent:
                _logger.info("Nómina %s ya fue procesada. Omitiendo...", payslip.name)
                continue
                
            try:
                # Generar documento y adjunto
                doc = payslip._generate_document_and_attachment()
                
                # Enviar correo
                email_sent = payslip._send_email()
                
                # Marcar como enviado (incluso si el correo falló, el documento se creó)
                payslip.x_doc_sent = True
                
                if email_sent:
                    payslip.message_post(
                        body=_("✅ Documento generado y correo enviado exitosamente."),
                        message_type='notification',
                    )
                else:
                    payslip.message_post(
                        body=_("⚠️ Documento generado pero no se pudo enviar el correo (revisar email del empleado)."),
                        message_type='notification',
                    )
                    
            except Exception as e:
                _logger.error("Error en automatización de nómina para %s: %s", payslip.name, e, exc_info=True)
                payslip.message_post(
                    body=_("❌ Error generando documento: %s") % str(e),
                    message_type='notification',
                )

    def action_generate_document_manual(self):
        """Solo genera/asegura PDF y Documents (acción manual)."""
        for payslip in self:
            try:
                doc = payslip._generate_document_and_attachment()
                payslip.message_post(
                    body=_("📄 Documento generado manualmente: %s") % doc.name,
                    message_type='notification',
                )
            except Exception as e:
                _logger.error("Error en generación de documento para %s: %s", payslip.name, e, exc_info=True)
                raise UserError(_("Error generando documento: %s") % str(e))

    def action_send_email_manual(self):
        """Solo envío manual de correo."""
        for payslip in self:
            email_sent = payslip._send_email()
            if email_sent:
                payslip.x_doc_sent = True
                payslip.message_post(
                    body=_("📧 Correo enviado manualmente."),
                    message_type='notification',
                )
            else:
                raise UserError(_(
                    "No se pudo enviar el correo para %s. "
                    "Verifica que el empleado tenga un email configurado."
                ) % payslip.employee_id.name)
