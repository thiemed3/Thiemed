from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSaleOrderDuplicateMessage(TransactionCase):

    def test_copy_posts_origin_message(self):
        partner = self.env['res.partner'].create({'name': 'Duplicate Partner Test'})
        order = self.env['sale.order'].create({'partner_id': partner.id})

        duplicated = order.copy()

        body = ' '.join(duplicated.message_ids.mapped('body'))
        self.assertIn(order.display_name, body)
        self.assertIn('duplic', body.lower())


@tagged('post_install', '-at_install')
class TestSaleOrderDuplicateMessageUI(TransactionCase):

    def test_message_template_is_valid(self):
        template = self.env.ref('sale_order_duplicate_message.sale_order_duplicate_origin_message')

        template._check_xml()
        arch = etree.tostring(template._get_combined_arch(), encoding='unicode')

        self.assertIn('origin.display_name', arch)
        self.assertIn('origin._name', arch)
        self.assertIn('origin.id', arch)
