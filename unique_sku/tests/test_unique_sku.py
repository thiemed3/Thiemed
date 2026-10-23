from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestUniqueSku(TransactionCase):

    def test_product_template_default_code_must_be_unique(self):
        self.env['product.template'].create({
            'name': 'Unique SKU Test 1',
            'default_code': 'UNIQUE-SKU-TEST',
        })

        with self.assertRaises(ValidationError):
            self.env['product.template'].create({
                'name': 'Unique SKU Test 2',
                'default_code': 'UNIQUE-SKU-TEST',
            })

    def test_product_template_default_code_write_must_be_unique(self):
        self.env['product.template'].create({
            'name': 'Unique SKU Write Test 1',
            'default_code': 'UNIQUE-SKU-WRITE-TEST',
        })
        product_2 = self.env['product.template'].create({
            'name': 'Unique SKU Write Test 2',
        })

        with self.assertRaises(ValidationError):
            product_2.write({'default_code': 'UNIQUE-SKU-WRITE-TEST'})

    def test_empty_default_code_can_be_reused(self):
        product_1 = self.env['product.template'].create({'name': 'Unique SKU Empty 1'})
        product_2 = self.env['product.template'].create({'name': 'Unique SKU Empty 2'})

        self.assertFalse(product_1.default_code)
        self.assertFalse(product_2.default_code)


@tagged('post_install', '-at_install')
class TestUniqueSkuUI(TransactionCase):

    def test_product_views_are_valid(self):
        views = self.env['ir.ui.view'].browse([
            self.env.ref('product.product_template_form_view').id,
            self.env.ref('product.product_template_tree_view').id,
            self.env.ref('product.product_search_form_view').id,
        ])

        for view in views:
            view._check_xml()

    def test_product_template_form_contains_internal_reference(self):
        view = self.env.ref('product.product_template_only_form_view')
        combined_arch = view._get_combined_arch()

        self.assertTrue(combined_arch.xpath("//field[@name='default_code']"))
