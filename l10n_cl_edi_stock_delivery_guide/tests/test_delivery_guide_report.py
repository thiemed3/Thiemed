from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDeliveryGuideReport(TransactionCase):

    def test_loaded_report_templates_are_valid(self):
        views = self.env['ir.ui.view'].browse([
            self.env.ref('l10n_cl_edi_stock_delivery_guide.delivery_guide_cedible').id,
            self.env.ref('l10n_cl_edi_stock_delivery_guide.delivery_guide_document_content').id,
            self.env.ref('l10n_cl_edi_stock_delivery_guide.delivery_guide_document_inherit').id,
        ])

        for view in views:
            view._check_xml()

    def test_delivery_guide_report_adds_cedible_copy(self):
        view = self.env.ref('l10n_cl_edi_stock_delivery_guide.delivery_guide_document_content')

        combined_arch = etree.tostring(view._get_combined_arch(), encoding='unicode')

        self.assertIn('CEDIBLE CON SU FACTURA', combined_arch)
        self.assertIn("prepared_amounts.get('withholdings'", view.arch_db)

    def test_delivery_guide_report_renders_cedible_copy(self):
        product = self.env['product.product'].create({
            'name': 'Producto Guía Cedible',
            'is_storable': True,
            'list_price': 1000.0,
        })
        partner = self.env['res.partner'].create({
            'name': 'Cliente Guía Cedible',
            'country_id': self.env.ref('base.cl').id,
        })
        picking = self.env['stock.picking'].create({
            'partner_id': partner.id,
            'location_id': self.env.ref('stock.stock_location_stock').id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'picking_type_id': self.env.ref('stock.picking_type_out').id,
            'l10n_latam_document_number': '1',
        })
        self.env['stock.move'].create({
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': 1.0,
            'quantity': 1.0,
            'picking_id': picking.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
        })
        report = self.env.ref('l10n_cl_edi_stock.action_delivery_guide_report_pdf')

        html, _ = report._render_qweb_html(report.report_name, [picking.id])
        html = html.decode() if isinstance(html, bytes) else html

        self.assertIn('Nombre:', html)
        self.assertIn('CEDIBLE', html)
