from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReportSaleOrderDelivered(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Delivered Report Partner'})
        cls.product = cls.env['product.product'].create({
            'name': 'Delivered Report Product',
            'sale_ok': True,
            'list_price': 100.0,
        })

    def _create_order(self, include_undelivered=False):
        lines = [(0, 0, {
            'product_id': self.product.id,
            'product_uom_qty': 2.0,
            'qty_delivered': 1.0,
            'price_unit': 100.0,
        })]
        if include_undelivered:
            undelivered_product = self.env['product.product'].create({
                'name': 'Undelivered Report Product',
                'sale_ok': True,
                'list_price': 50.0,
            })
            lines.append((0, 0, {
                'product_id': undelivered_product.id,
                'product_uom_qty': 1.0,
                'qty_delivered': 0.0,
                'price_unit': 50.0,
            }))
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': lines,
        })

    def test_report_action_is_available(self):
        action = self.env.ref('report_sale_order_delivered.action_report_saleorder_delivered')

        self.assertEqual(action.model, 'sale.order')
        self.assertEqual(action.report_name, 'report_sale_order_delivered.report_saleorder_delivered')

    def test_report_renders_with_delivered_quantities(self):
        order = self._create_order(include_undelivered=True)
        report = self.env.ref('report_sale_order_delivered.action_report_saleorder_delivered')

        html, _ = report._render_qweb_html(
            'report_sale_order_delivered.report_saleorder_delivered',
            [order.id],
        )

        self.assertIn(b'Delivered Report Product', html)
        self.assertNotIn(b'Undelivered Report Product', html)
        self.assertIn(b'100', html)


@tagged('post_install', '-at_install')
class TestReportSaleOrderDeliveredUI(TransactionCase):

    def test_report_views_are_valid(self):
        views = self.env['ir.ui.view'].browse([
            self.env.ref('report_sale_order_delivered.report_saleorder_delivered_document').id,
            self.env.ref('report_sale_order_delivered.report_saleorder_delivered').id,
        ])

        for view in views:
            view._check_xml()

    def test_report_template_uses_odoo_19_sale_fields(self):
        view = self.env.ref('report_sale_order_delivered.report_saleorder_delivered_document')

        arch = etree.tostring(view._get_combined_arch(), encoding='unicode')

        self.assertIn('line.product_uom_id', arch)
        self.assertIn('line.tax_ids', arch)
        self.assertIn('line.qty_delivered &gt; 0', arch)
