from odoo import api, models


class GeneralPayrollReport(models.AbstractModel):
    _inherit = "report.l10n_cl_hr.report_payslipgeneral"

    @api.model
    def _get_report_values(self, docids, data=None):
        self.env["hr.payslip.run"].browse(docids)._check_general_report_access()
        return super()._get_report_values(docids, data=data)
