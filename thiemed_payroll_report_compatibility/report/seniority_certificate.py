from odoo import api, models


class SeniorityCertificateReport(models.AbstractModel):
    _name = "report.l10n_cl_hr_payroll_reports.report_certificado_antiguedad"
    _description = "Certificado de Antigüedad: acceso y versión laboral"

    @api.model
    def _get_report_values(self, docids, data=None):
        version = self.env["hr.version"].browse(docids)
        version._check_seniority_report_access()
        return {
            "doc_ids": version.ids,
            "doc_model": "hr.version",
            "docs": version.with_context(version_id=version.id),
            "data": data,
        }
