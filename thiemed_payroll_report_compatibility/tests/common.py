from io import BytesIO
from unittest import SkipTest

from PyPDF2 import PdfReader

from odoo import Command, fields
from odoo.tests.common import new_test_user


PROTECTED_TABLES = (
    "hr_employee",
    "hr_version",
    "hr_payslip_run",
    "hr_payslip",
    "hr_payslip_line",
    "hr_payslip_input",
    "hr_payslip_worked_days",
    "hr_salary_rule",
    "hr_payroll_structure",
    "account_move",
    "account_move_line",
)


def payroll_snapshot(env):
    result = {}
    for table in PROTECTED_TABLES:
        env.cr.execute(
            f"SELECT count(*), md5(string_agg(md5(row_to_json(t)::text), '' ORDER BY id)) "
            f"FROM {table} t"
        )
        result[table] = env.cr.fetchone()
    return result


def pdf_text(content):
    reader = PdfReader(BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


class ReportDataMixin:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.payroll_run = cls.env["hr.payslip.run"].search([
            ("date_start", "=", "2026-09-01"),
            ("date_end", "=", "2026-09-30"),
            ("slip_ids", "!=", False),
        ], limit=1)
        if not cls.payroll_run:
            cls.payroll_run = cls.env["hr.payslip.run"].search([
                ("slip_ids", "!=", False),
            ], order="date_start desc", limit=1)
        if not cls.payroll_run:
            raise SkipTest("Se necesita una copia local con liquidaciones existentes.")
        cls.company = cls.payroll_run.company_id
        today = fields.Date.context_today(cls.env["hr.version"])
        versions = cls.env["hr.version"].search([
            ("company_id", "=", cls.company.id),
            ("employee_id.active", "=", True),
            ("contract_date_start", "<=", today),
            ("date_version", "<=", today),
            ("identification_id", "!=", False),
            ("job_id", "!=", False),
            ("contract_type_id", "!=", False),
        ], order="date_version desc")
        cls.version = versions.filtered(lambda v: not v.date_end or v.date_end >= today)[:1]
        if not cls.version:
            raise SkipTest("Se necesita un trabajador vigente con datos para el certificado.")
        cls.employee = cls.version.employee_id
        cls.other_company = cls.env["res.company"].search([
            ("id", "!=", cls.company.id),
        ], limit=1)
        cls.manager = new_test_user(
            cls.env,
            login=f"report_manager_{cls.__name__}",
            context={"no_reset_password": True},
            groups="base.group_user,hr_payroll.group_hr_payroll_manager",
            company_id=cls.company.id,
            company_ids=[Command.set(cls.company.ids)],
        )
        cls.officer = new_test_user(
            cls.env,
            login=f"report_officer_{cls.__name__}",
            context={"no_reset_password": True},
            groups="base.group_user,hr_payroll.group_hr_payroll_user",
            company_id=cls.company.id,
            company_ids=[Command.set(cls.company.ids)],
        )
        cls.reader = new_test_user(
            cls.env,
            login=f"report_reader_{cls.__name__}",
            context={"no_reset_password": True},
            groups="base.group_user",
            company_id=cls.company.id,
            company_ids=[Command.set(cls.company.ids)],
        )
        cls.general_report = cls.env.ref("l10n_cl_hr.payslip_general_report")
        cls.certificate_report = cls.env.ref(
            "l10n_cl_hr_payroll_reports.hr_payroll_certificados_antiguedad"
        )

    def as_user(self, records, user=None):
        return records.with_user(user or self.manager).with_context(
            allowed_company_ids=self.company.ids,
            lang="es_CL",
            report_pdf_no_attachment=True,
        )
