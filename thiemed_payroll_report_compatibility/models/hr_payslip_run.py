from odoo import models
from odoo.exceptions import AccessError, UserError


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    def _check_general_report_access(self):
        if not self.env.user.has_group("hr_payroll.group_hr_payroll_user"):
            raise AccessError(self.env._("No tiene permisos para imprimir Nómina general."))
        if len(self) != 1 or not self.exists():
            raise UserError(self.env._("Seleccione exactamente un periodo de nómina existente."))
        self.check_access("read")
        if self.company_id not in self.env.companies:
            raise AccessError(self.env._("La empresa del periodo no está autorizada."))
        if not self.date_start or not self.date_end or self.date_start > self.date_end:
            raise UserError(self.env._("El periodo no tiene fechas válidas."))

        slips = self.env["hr.payslip"].search([("payslip_run_id", "=", self.id)])
        # Only cardinality is read outside record rules, to reject a partial report.
        self.env.cr.execute(
            "SELECT count(*) FROM hr_payslip WHERE payslip_run_id = %s", (self.id,)
        )
        if len(slips) != self.env.cr.fetchone()[0]:
            raise AccessError(self.env._("No tiene acceso a todas las liquidaciones del periodo."))
        if not slips:
            raise UserError(self.env._("El periodo no contiene liquidaciones."))
        slips.check_access("read")
        for slip in slips:
            if slip.company_id != self.company_id:
                raise UserError(self.env._("El periodo contiene liquidaciones de otra empresa."))
            if (
                not slip.date_from
                or not slip.date_to
                or slip.date_from > slip.date_to
                or slip.date_from < self.date_start
                or slip.date_to > self.date_end
            ):
                raise UserError(self.env._("El periodo contiene liquidaciones con fechas incompatibles."))
            if not slip.line_ids:
                raise UserError(self.env._("El periodo contiene liquidaciones sin líneas calculadas."))

        lines = slips.line_ids
        lines.check_access("read")
        self.env.cr.execute(
            "SELECT count(*) FROM hr_payslip_line WHERE slip_id IN %s", (tuple(slips.ids),)
        )
        if len(lines) != self.env.cr.fetchone()[0]:
            raise AccessError(self.env._("No tiene acceso a todas las líneas de las liquidaciones."))
        return self

    def action_print_general_payroll(self):
        self._check_general_report_access()
        return self.env.ref("l10n_cl_hr.payslip_general_report").with_context(
            active_model="hr.payslip.run"
        ).report_action(self)
