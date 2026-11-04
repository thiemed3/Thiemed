from odoo import fields, models
from odoo.exceptions import AccessError, UserError


class HrVersion(models.Model):
    _inherit = "hr.version"

    def _check_seniority_report_access(self):
        if not self.env.user.has_group("hr.group_hr_manager"):
            raise AccessError(self.env._("No tiene permisos para imprimir el Certificado de Antigüedad."))
        if len(self) != 1 or not self.exists():
            raise UserError(self.env._("Seleccione exactamente una versión laboral existente."))
        self.check_access("read")
        if self.company_id not in self.env.companies:
            raise AccessError(self.env._("La empresa del trabajador no está autorizada."))
        employee = self.employee_id
        employee.check_access("read")
        if not employee or employee.company_id != self.company_id:
            raise UserError(self.env._("La versión no corresponde a un trabajador de esta empresa."))
        today = fields.Date.context_today(self)
        if (
            not self.active
            or not employee.active
            or not self.contract_date_start
            or self.contract_date_start > today
            or self.date_version > today
            or (self.contract_date_end and self.contract_date_end < today)
            or (self.date_end and self.date_end < today)
        ):
            raise UserError(self.env._("Seleccione una versión vigente con fecha de inicio de contrato."))

        company = self.company_id
        representative = company.legal_representative_id
        if not (
            employee.name
            and self.identification_id
            and self.job_id
            and self.contract_type_id
            and company.vat
            and company.city
            and representative.name
            and representative.vat
        ):
            raise UserError(self.env._(
                "Faltan datos del certificado: identificación, cargo, tipo de contrato, "
                "RUT o ciudad de la empresa, o nombre y RUT del representante legal."
            ))
        return self
