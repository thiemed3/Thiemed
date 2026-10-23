from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSaleOrderMedicalInformation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Paciente Test'})
        cls.doctor = cls.env['res.partner'].create({'name': 'Doctor Test'})
        cls.product = cls.env['product.product'].create({
            'name': 'Producto Medico Test',
            'is_storable': True,
            'list_price': 100.0,
        })

    def _create_sale_order(self):
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'partner_paciente': 'Paciente Operacion',
            'partner_doctor': self.doctor.id,
            'fecha_operacion': '2026-08-04 10:00:00',
            'tipo_venta': 'asistenciacirugia',
            'asistente_cirugia': self.env.user.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 100.0,
            })],
        })

    def test_prepare_invoice_includes_medical_information(self):
        order = self._create_sale_order()

        values = order._prepare_invoice()

        self.assertEqual(values['partner_paciente'], 'Paciente Operacion')
        self.assertEqual(values['partner_doctor'], self.doctor.id)
        self.assertEqual(values['fecha_operacion'], order.fecha_operacion)
        self.assertEqual(values['tipo_venta'], 'asistenciacirugia')
        self.assertEqual(values['asistente_cirugia'], self.env.user.id)

    def test_confirm_sale_propagates_medical_information_to_picking(self):
        order = self._create_sale_order()

        order.action_confirm()

        self.assertTrue(order.picking_ids)
        picking = order.picking_ids[:1]
        self.assertEqual(picking.partner_paciente, order.partner_paciente)
        self.assertEqual(picking.partner_doctor, order.partner_doctor)
        self.assertEqual(picking.fecha_operacion, order.fecha_operacion)
        self.assertEqual(picking.tipo_venta, order.tipo_venta)
        self.assertEqual(picking.asistente_cirugia, order.asistente_cirugia)


@tagged('post_install', '-at_install')
class TestSaleOrderMedicalInformationViews(TransactionCase):

    def test_form_views_are_valid(self):
        views = self.env['ir.ui.view'].browse([
            self.env.ref('sale_order_medical_information.sale_order_doc_form').id,
            self.env.ref('sale_order_medical_information.stock_picking_doc').id,
            self.env.ref('sale_order_medical_information.account_move_doc_form').id,
        ])

        for view in views:
            view._check_xml()
            combined_arch = etree.tostring(view._get_combined_arch(), encoding='unicode')
            self.assertIn('tipo_venta', combined_arch)
