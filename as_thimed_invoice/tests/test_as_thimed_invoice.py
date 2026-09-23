from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAsThimedInvoice(TransactionCase):

    def test_res_config_settings_uses_config_parameter(self):
        settings = self.env['res.config.settings'].create({
            'as_fecha_invenatario': '2026-01-15',
        })

        settings.execute()

        value = self.env['ir.config_parameter'].sudo().get_param(
            'res_config_settings.as_fecha_invenatario'
        )
        self.assertEqual(value, '2026-01-15')


@tagged('post_install', '-at_install')
class TestAsThimedInvoiceUI(TransactionCase):

    def test_loaded_views_are_valid(self):
        views = self.env['ir.ui.view'].browse([
            self.env.ref('as_thimed_invoice.view_order_ref_form').id,
            self.env.ref('as_thimed_invoice.view_account_move_ref_form').id,
            self.env.ref('as_thimed_invoice.as_sale_pricelist_form_view').id,
            self.env.ref('as_thimed_invoice.view_stock_landed_cost_form_inherit').id,
            self.env.ref('as_thimed_invoice.res_config_settings_view_form').id,
            self.env.ref('as_thimed_invoice.stock_report_deliveryslip_inherit_product_expiry').id,
            self.env.ref('as_thimed_invoice.report_invoice_cedible_wrapper').id,
            self.env.ref('as_thimed_invoice.report_invoice_document_cedible').id,
        ])

        for view in views:
            view._check_xml()

    def test_delivery_report_contains_note_extension(self):
        view = self.env.ref('stock.report_delivery_document')

        combined_arch = etree.tostring(view._get_combined_arch(), encoding='unicode')

        self.assertIn('o.note', combined_arch)

    def test_invoice_report_action_is_available(self):
        action = self.env.ref('as_thimed_invoice.report_invoice_cedible')

        self.assertEqual(action.model, 'account.move')
        self.assertEqual(action.report_type, 'qweb-pdf')
        self.assertEqual(action.report_name, 'as_thimed_invoice.report_invoice_cedible_wrapper')

    def test_invoice_cedible_report_renders(self):
        account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
        ], limit=1)
        if not account:
            self.skipTest('No income account available to create an invoice')

        partner = self.env['res.partner'].create({
            'name': 'Cliente Factura Cedible',
            'country_id': self.env.ref('base.cl').id,
        })
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Producto factura cedible',
                'quantity': 1,
                'price_unit': 1000,
                'account_id': account.id,
            })],
        })
        action = self.env.ref('as_thimed_invoice.report_invoice_cedible')

        html, _ = action._render_qweb_html(action.report_name, [invoice.id])
        html = html.decode() if isinstance(html, bytes) else html

        self.assertIn('CEDIBLE', html)
