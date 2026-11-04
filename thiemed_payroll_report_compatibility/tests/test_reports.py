from collections import defaultdict
from datetime import timedelta
from unittest.mock import patch

from lxml import etree

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import format_date

from .common import ReportDataMixin
from .footer_checks import validate_footer_layouts


@tagged("post_install", "-at_install", "thiemed_payroll_reports")
class TestPayrollReportCompatibility(ReportDataMixin, TransactionCase):
    def test_private_footers_preserve_global_layouts_and_contact_data(self):
        self.assertTrue(validate_footer_layouts(self.env)['scoped'])

    def test_existing_actions_and_independent_views(self):
        for report in (self.general_report, self.certificate_report):
            self.assertEqual(self.env["ir.actions.report"].search_count([
                ("report_name", "=", report.report_name),
            ]), 1)
        self.assertEqual(self.general_report.model, "hr.payslip.run")
        self.assertEqual(self.certificate_report.model, "hr.version")
        standard = self.env.ref("hr_payroll.action_hr_payslip_run")
        self.assertEqual(standard.view_mode, "kanban,calendar,pivot,graph")
        action = self.env.ref("thiemed_payroll_report_compatibility.action_general_payroll_runs")
        self.assertEqual(action.view_mode, "list,form")
        self.assertEqual(len(action.view_ids), 2)
        for view in action.view_ids.view_id:
            arch = etree.fromstring(view.arch_db)
            self.assertEqual(arch.get("create"), "0")
            self.assertEqual(arch.get("edit"), "0")
            self.assertEqual(arch.get("delete"), "0")
            self.assertFalse(arch.get("js_class"))
        menu = self.env.ref("thiemed_payroll_report_compatibility.menu_general_payroll")
        self.assertEqual(menu.parent_id, self.env.ref("hr_payroll.menu_hr_payroll_report"))

    def test_actions_use_period_and_version_ids(self):
        action = self.as_user(self.payroll_run, self.officer).action_print_general_payroll()
        self.assertEqual(action["type"], "ir.actions.report")
        self.assertEqual(action["report_name"], self.general_report.report_name)
        self.assertEqual(action["context"]["active_ids"], self.payroll_run.ids)
        self.assertEqual(action["context"]["active_model"], "hr.payslip.run")
        action = self.as_user(self.employee).with_context(
            version_id=self.version.id
        ).action_print_seniority_certificate()
        self.assertEqual(action["report_name"], self.certificate_report.report_name)
        self.assertEqual(action["context"]["active_ids"], self.version.ids)
        self.assertEqual(action["context"]["active_model"], "hr.version")
        self.assertTrue(action["context"]["report_pdf_no_attachment"])

    def test_single_period_and_existing_records_required(self):
        model = self.as_user(self.env["report.l10n_cl_hr.report_payslipgeneral"])
        for ids in ([], [self.payroll_run.id, self.payroll_run.id], [2147483647]):
            with self.subTest(ids=ids), self.assertRaises(UserError):
                model._get_report_values(ids)

    def test_certificate_resolves_current_version_without_context(self):
        expected = self.as_user(self.employee)._get_version(fields.Date.context_today(self.employee))
        action = self.as_user(self.employee).with_context(
            version_id=False
        ).action_print_seniority_certificate()
        self.assertEqual(action["context"]["active_ids"], expected.ids)

    def test_invalid_period_dates_are_rejected_without_writes(self):
        with patch.object(type(self.payroll_run), "date_end", property(lambda run: run.date_start - timedelta(days=1))):
            with self.assertRaises(UserError):
                self.as_user(self.payroll_run).action_print_general_payroll()

    def test_slips_outside_period_are_rejected_without_writes(self):
        with patch.object(type(self.payroll_run), "date_end", property(lambda run: run.date_start)):
            with self.assertRaises(UserError):
                self.as_user(self.payroll_run).action_print_general_payroll()

    def test_mixed_company_slips_are_rejected_without_writes(self):
        if not self.other_company:
            self.skipTest("Se necesitan dos empresas existentes.")
        other = self.other_company
        with patch.object(type(self.env["hr.payslip"]), "company_id", property(lambda slip: other)):
            with self.assertRaises(UserError):
                self.as_user(self.payroll_run).action_print_general_payroll()

    def test_restricted_slip_rule_cannot_produce_partial_report(self):
        self.env["ir.rule"].create({
            "name": "Test: ocultar una liquidación del consolidado",
            "model_id": self.env["ir.model"]._get_id("hr.payslip"),
            "domain_force": repr([("id", "!=", self.payroll_run.slip_ids[0].id)]),
        })
        with self.assertRaises(AccessError):
            self.as_user(self.payroll_run).action_print_general_payroll()

    def test_restricted_line_rule_cannot_produce_partial_report(self):
        self.env["ir.rule"].create({
            "name": "Test: ocultar una línea del consolidado",
            "model_id": self.env["ir.model"]._get_id("hr.payslip.line"),
            "domain_force": repr([("id", "!=", self.payroll_run.slip_ids.line_ids[0].id)]),
        })
        with self.assertRaises(AccessError):
            self.as_user(self.payroll_run).action_print_general_payroll()

    def test_permissions_apply_to_buttons_and_direct_rendering(self):
        reports = self.as_user(self.env["ir.actions.report"], self.reader)
        for report, records in ((self.general_report, self.payroll_run), (self.certificate_report, self.version)):
            with self.subTest(report=report.report_name), self.assertRaises(AccessError):
                reports._render_qweb_html(report.report_name, records.ids)
        with self.assertRaises(AccessError):
            self.as_user(self.payroll_run, self.reader).action_print_general_payroll()
        with self.assertRaises(AccessError):
            self.as_user(self.employee, self.reader).action_print_seniority_certificate()

    def test_other_company_is_denied(self):
        if not self.other_company:
            self.skipTest("Se necesitan dos empresas existentes.")
        for records, method in (
            (self.payroll_run, "action_print_general_payroll"),
            (self.employee, "action_print_seniority_certificate"),
        ):
            with self.subTest(model=records._name), self.assertRaises(AccessError):
                getattr(records.with_user(self.manager).with_context(
                    allowed_company_ids=self.other_company.ids
                ), method)()

    def test_certificate_rejects_foreign_and_invalid_versions(self):
        other = self.env["hr.version"].search([
            ("company_id", "=", self.company.id),
            ("employee_id", "!=", self.employee.id),
            ("employee_id", "!=", False),
        ], limit=1)
        for version_id in (2147483647, "invalid", True, other.id if other else 2147483647):
            with self.subTest(version_id=version_id), self.assertRaises(UserError):
                self.as_user(self.employee).with_context(
                    version_id=version_id
                ).action_print_seniority_certificate()

    def test_certificate_rejects_historical_future_and_incomplete_versions(self):
        today = fields.Date.context_today(self.version)
        cases = {
            "date_end": today - timedelta(days=1),
            "date_version": today + timedelta(days=1),
            "contract_date_start": False,
            "identification_id": False,
            "active": False,
        }
        for name, value in cases.items():
            with self.subTest(field=name), patch.object(
                type(self.version), name, property(lambda record, v=value: v)
            ), self.assertRaises(UserError):
                self.as_user(self.env["ir.actions.report"])._render_qweb_html(
                    self.certificate_report.report_name, self.version.ids
                )

    def test_certificate_uses_contract_start_not_version_start(self):
        self.as_user(self.version).date_end
        with patch.object(type(self.version), "date_start", property(lambda record: fields.Date.today())):
            html, _ = self.as_user(self.env["ir.actions.report"])._render_qweb_html(
                self.certificate_report.report_name, self.version.ids
            )
        root = etree.HTML(html)
        text = " ".join(" ".join(root.itertext()).split())
        expected = format_date(
            self.env, self.version.contract_date_start,
            lang_code=self.employee.lang or "es_CL", date_format="dd 'de' MMMM 'de' YYYY",
        )
        self.assertIn(expected, text)
        self.assertIn(self.version.identification_id, text)

    def test_general_report_matches_stored_lines_for_every_section(self):
        values = self.as_user(self.env["report.l10n_cl_hr.report_payslipgeneral"])._get_report_values(self.payroll_run.ids)
        self.env.cr.execute("""
            SELECT l.name, r.use, c.code, r.appears_on_payslip, l.total
              FROM hr_payslip_line l
              JOIN hr_payslip p ON p.id = l.slip_id
              JOIN hr_salary_rule r ON r.id = l.salary_rule_id
              JOIN hr_salary_rule_category c ON c.id = r.category_id
             WHERE p.payslip_run_id = %s
        """, (self.payroll_run.id,))
        rows = self.env.cr.fetchall()
        sections = {
            "get_details_by_total_ganado": {"base", "grat", "hextra", "otroimp"},
            "get_details_by_total_haberes": {"cargas", "mov", "col", "otronoimp"},
            "get_details_by_total_descuento": {"retsii", "afp", "salud", "adsalud", "impunico", "segces", "otrodcto", "otrodctoleg"},
            "get_total_haberes": {"totalhab"},
            "get_total_ganado": {"sueldoimp"},
            "get_anticipo": {"anticipo"},
            "get_liquido": {"liquido"},
        }
        for key, uses in sections.items():
            expected = defaultdict(float)
            for name, use, category, visible, total in rows:
                if visible and use in uses:
                    expected[name] += total
            actual = {row["name"]: row["value"] for row in values[key][self.payroll_run.id]}
            with self.subTest(section=key):
                self.assertEqual(actual, dict(expected))
        expected_patronal = defaultdict(float)
        for name, use, category, visible, total in rows:
            if category == "PATRONAL":
                expected_patronal[name] += total
        actual = {row["name"]: row["value"] for row in values["get_details_by_total_desc_libro"][self.payroll_run.id]}
        self.assertEqual(actual, dict(expected_patronal))
        self.assertAlmostEqual(values["get_total_desc_libro"][self.payroll_run.id][0]["value"], sum(expected_patronal.values()))
        discounts = sections["get_details_by_total_descuento"]
        self.assertAlmostEqual(values["get_total_descuento"][self.payroll_run.id][0]["value"], sum(row[4] for row in rows if row[1] in discounts))
