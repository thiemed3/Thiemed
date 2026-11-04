import json

from lxml import etree

from odoo.tests import HttpCase, tagged

from .common import ReportDataMixin, payroll_snapshot, pdf_text


@tagged("post_install", "-at_install", "thiemed_payroll_reports")
class TestPayrollReportHTTP(ReportDataMixin, HttpCase):
    def rpc(self, path, params):
        response = self.url_open(path, data=json.dumps({
            "jsonrpc": "2.0", "method": "call", "params": params, "id": 1,
        }), headers={"Content-Type": "application/json"})
        payload = response.json()
        self.assertNotIn("error", payload, payload)
        return payload["result"]

    def test_interface_actions_and_pdf_downloads(self):
        self.authenticate(self.manager.login, self.manager.login)
        self.env.flush_all()
        before = payroll_snapshot(self.env)
        attachments_before = self.env["ir.attachment"].search_count([
            ("res_model", "in", ["hr.version", "hr.payslip.run"]),
        ])
        menus = self.rpc("/web/dataset/call_kw/ir.ui.menu/load_menus", {
            "model": "ir.ui.menu", "method": "load_menus", "args": [False], "kwargs": {},
        })
        menu = self.env.ref("thiemed_payroll_report_compatibility.menu_general_payroll")
        self.assertIn(str(menu.id), menus)
        for model, record, method, expected in (
            ("hr.payslip.run", self.payroll_run, "action_print_general_payroll", "LIQUIDACIÓN GENERAL"),
            ("hr.employee", self.employee, "action_print_seniority_certificate", "CERTIFICADO DE ANTIGÜEDAD"),
        ):
            action = self.rpc(f"/web/dataset/call_button/{model}/{method}", {
                "model": model, "method": method, "args": [record.ids],
                "kwargs": {"context": {
                    "allowed_company_ids": self.company.ids, "lang": "es_CL",
                    "version_id": self.version.id if model == "hr.employee" else False,
                }},
            })
            ids = ",".join(map(str, action["context"]["active_ids"]))
            context = dict(action["context"], force_report_rendering=True)
            response = self.url_open(
                f"/report/pdf/{action['report_name']}/{ids}",
                params={"context": json.dumps(context)},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["Content-Type"], "application/pdf")
            text = pdf_text(response.content)
            self.assertIn(expected, text)
            if model == "hr.employee":
                self.assertIn(self.employee.name.upper(), text)
                self.assertIn(self.version.identification_id, text)
        view = self.as_user(self.env["hr.employee"]).get_view(
            view_id=self.env.ref("hr.view_employee_form").id, view_type="form"
        )
        self.assertTrue(etree.fromstring(view["arch"]).xpath(
            "//button[@name='action_print_seniority_certificate']"
        ))
        self.env.flush_all()
        self.assertEqual(before, payroll_snapshot(self.env))
        self.assertEqual(attachments_before, self.env["ir.attachment"].search_count([
            ("res_model", "in", ["hr.version", "hr.payslip.run"]),
        ]))

    def test_unauthorized_user_cannot_download_either_report(self):
        self.authenticate(self.reader.login, self.reader.login)
        for report, record in ((self.general_report, self.payroll_run), (self.certificate_report, self.version)):
            response = self.url_open(f"/report/pdf/{report.report_name}/{record.id}", params={
                "context": json.dumps({"force_report_rendering": True, "report_pdf_no_attachment": True}),
            })
            self.assertFalse(response.content.startswith(b"%PDF-"))
            self.assertGreaterEqual(response.status_code, 400)
