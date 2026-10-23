from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestL10nClEdiAccountAccountantReports(TransactionCase):

    def test_loaded_report_templates_are_valid(self):
        views = self.env['ir.ui.view'].browse([
            self.env.ref('l10n_cl_edi_account_accountant.delivery_guide_cedible').id,
            self.env.ref('l10n_cl_edi_account_accountant.cedible_footer').id,
            self.env.ref('l10n_cl_edi_account_accountant.report_invoice_inherit').id,
        ])

        for view in views:
            view._check_xml()

    def test_invoice_report_adds_cedible_copy(self):
        invoice_view = self.env.ref('account.report_invoice')
        cedible_footer = self.env.ref('l10n_cl_edi_account_accountant.cedible_footer')

        report_arch = etree.tostring(invoice_view._get_combined_arch(), encoding='unicode')

        self.assertIn('CEDIBLE CON SU FACTURA', report_arch)
        self.assertIn('l10n_cl_edi_account_accountant.delivery_guide_cedible', cedible_footer.arch_db)

    def test_invoice_report_renders_cedible_copy(self):
        account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
        ], limit=1)
        if not account:
            self.skipTest('No income account available to create an invoice')

        partner = self.env['res.partner'].create({
            'name': 'Cliente Cedible',
            'country_id': self.env.ref('base.cl').id,
        })
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Producto cedible',
                'quantity': 1,
                'price_unit': 1000,
                'account_id': account.id,
            })],
        })
        report = self.env.ref('account.account_invoices_without_payment')

        html, _ = report._render_qweb_html(report.report_name, [invoice.id])
        html = html.decode() if isinstance(html, bytes) else html

        self.assertIn('Nombre:', html)
        self.assertIn('CEDIBLE', html)
