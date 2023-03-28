# test que valida que se cree una cuenta analitica al crear una venta
# tambien valida que se desactive la cuenta analitica al cancelar la venta
# y que se active la cuenta analitica al volver a confirmar la venta
# tambien valida que no se pueda eliminar la cuenta analitica desde el pedido de venta

from odoo.tests.common import TransactionCase, tagged, Form
from odoo.exceptions import UserError

@tagged('post_install', '-at_install', 'sale_auto_analytic')
class TestSaleOrder(TransactionCase):

        def setUp(self):
            super(TestSaleOrder, self).setUp()
            self.sale_order = self.env['sale.order']
            self.partner = self.env['res.partner'].create({
                'name': 'Test Partner',
                'email': 'admin@admin.com',
                'phone': '123456789',
            })
            self.product = self.env['product.product'].create({
                'name': 'Test Product',
                'type': 'service',
                'list_price': 100,
            })
            self.product2 = self.env['product.product'].create({
                'name': 'Test Product 2',
                'type': 'service',
                'list_price': 100,
            })

        def test_create_sale_order(self):
            # creamos un pedido de venta
            sale_order = self.sale_order.create({
                'partner_id': self.partner.id,
                'order_line': [(0, 0, {
                    'product_id': self.product.id,
                    'product_uom_qty': 1,
                    'price_unit': 100,
                })]
            })
            # verificamos que se haya creado el pedido de venta
            self.assertTrue(sale_order)
            # verificamos que se haya creado la cuenta analitica
            self.assertTrue(sale_order.analytic_account_id)
            # verificamos que la cuenta analitica tenga el mismo nombre que el pedido de venta
            self.assertEqual(sale_order.analytic_account_id.name, sale_order.name)
            # verificamos que la cuenta analitica tenga el mismo partner que el pedido de venta
            self.assertEqual(sale_order.analytic_account_id.partner_id.id, sale_order.partner_id.id)
            # verificamos que la cuenta analitica tenga el mismo codigo que el pedido de venta
            self.assertEqual(sale_order.analytic_account_id.code, sale_order.name)
            # verificamos que la cuenta analitica este activa
            self.assertTrue(sale_order.analytic_account_id.active)

        def test_cancel_sale_order(self):
            # creamos un pedido de venta
            sale_order = self.sale_order.create({
                'partner_id': self.partner.id,
                'order_line': [(0, 0, {
                    'product_id': self.product.id,
                    'product_uom_qty': 1,
                    'price_unit': 100,
                })]
            })
            # verificamos que se haya creado el pedido de venta
            self.assertTrue(sale_order)
            # verificamos que se haya creado la cuenta analitica
            self.assertTrue(sale_order.analytic_account_id)
            # verificamos que la cuenta analitica este activa
            self.assertTrue(sale_order.analytic_account_id.active)
            # cancelamos el pedido de venta
            sale_order.action_cancel()
            # verificamos que la cuenta analitica no este activa
            self.assertFalse(sale_order.analytic_account_id.active)

        def test_draft_sale_order(self):
            # creamos un pedido de venta
            sale_order = self.sale_order.create({
                'partner_id': self.partner.id,
                'order_line': [(0, 0, {
                    'product_id': self.product.id,
                    'product_uom_qty': 1,
                    'price_unit': 100,
                })]
            })
            # verificamos que se haya creado el pedido de venta
            self.assertTrue(sale_order)
            # verificamos que se haya creado la cuenta analitica
            self.assertTrue(sale_order.analytic_account_id)
            # verificamos que la cuenta analitica este activa
            self.assertTrue(sale_order.analytic_account_id.active)
            # cancelamos el pedido de venta
            sale_order.action_cancel()
            # verificamos que la cuenta analitica no este activa
            self.assertFalse(sale_order.analytic_account_id.active)
            # volvemos a confirmar el pedido de venta
            sale_order.action_draft()
            # verificamos que la cuenta analitica este activa
            self.assertTrue(sale_order.analytic_account_id.active)

        def test_delete_sale_order(self):
            # creamos un pedido de venta
            sale_order = self.sale_order.create({
                'partner_id': self.partner.id,
                'order_line': [(0, 0, {
                    'product_id': self.product.id,
                    'product_uom_qty': 1,
                    'price_unit': 100,
                })]
            })
            # verificamos que se haya creado el pedido de venta
            self.assertTrue(sale_order)
            # verificamos que se haya creado la cuenta analitica
            self.assertTrue(sale_order.analytic_account_id)
            # verificamos que la cuenta analitica este activa
            self.assertTrue(sale_order.analytic_account_id.active)
            # intentamos quitar el valor de la cuenta analitica desde el formulario del pedido de venta
            with Form(sale_order) as f:
                with self.assertRaises(AssertionError):
                    f.analytic_account_id = False
            # verificamos que no se haya podido quitar el valor de la cuenta analitica
            self.assertTrue(sale_order.analytic_account_id)
