from odoo import fields, models
from odoo.exceptions import AccessError, UserError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def action_print_seniority_certificate(self):
        if not self.env.user.has_group("hr.group_hr_manager"):
            raise AccessError(self.env._("No tiene permisos para imprimir el Certificado de Antigüedad."))
        if len(self) != 1 or not self.exists():
            raise UserError(self.env._("Seleccione exactamente un trabajador existente."))
        self.check_access("read")
        version_id = self.env.context.get("version_id")
        if version_id:
            if not isinstance(version_id, int) or isinstance(version_id, bool):
                raise UserError(self.env._("La versión laboral seleccionada no es válida."))
            version = self.env["hr.version"].browse(version_id)
        else:
            version = self._get_version(fields.Date.context_today(self))
        version._check_seniority_report_access()
        if version.employee_id != self:
            raise UserError(self.env._("La versión laboral no pertenece al trabajador seleccionado."))
        report = self.env.ref(
            "l10n_cl_hr_payroll_reports.hr_payroll_certificados_antiguedad"
        )
        return report.with_context(
            active_model="hr.version",
            version_id=version.id,
            report_pdf_no_attachment=True,
        ).report_action(version)
