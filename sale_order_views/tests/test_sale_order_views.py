from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSaleOrderViews(TransactionCase):

    def test_inherited_view_is_valid(self):
        view = self.env.ref('sale_order_views.sale_order_no_create_form_inherit')

        view._check_xml()

    def test_sale_order_form_disables_quick_create(self):
        view = self.env.ref('sale.view_order_form')

        combined_arch = view._get_combined_arch()

        fields = [
            "//field[@name='partner_id']",
            "//field[@name='order_line']//list//field[@name='product_template_id']",
            "//field[@name='order_line']//list//field[@name='product_id']",
        ]

        for expression in fields:
            nodes = combined_arch.xpath(expression)
            self.assertTrue(nodes, expression)
            self.assertTrue(
                any("'no_create': True" in (node.get('options') or '') for node in nodes),
                expression,
            )
