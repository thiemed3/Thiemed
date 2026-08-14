from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPickingReferences(TransactionCase):

    def test_reference_model_uses_odoo_19_model(self):
        field = self.env['stock.picking']._fields['l10n_cl_reference_ids']

        self.assertEqual(field.comodel_name, 'l10n_cl.edi.reference')
        self.assertIn('picking_id', self.env['l10n_cl.edi.reference']._fields)

    def test_sale_order_has_reference_date(self):
        self.assertIn('date_dte', self.env['sale.order']._fields)


@tagged('post_install', '-at_install')
class TestPickingReferencesUI(TransactionCase):

    def test_loaded_views_are_valid(self):
        views = self.env['ir.ui.view'].browse([
            self.env.ref('l10n_cl_picking_references.stock_picking_doc').id,
            self.env.ref('l10n_cl_picking_references.report_delivery_guide_inherit').id,
            self.env.ref('l10n_cl_picking_references.dte_subtemplate').id,
            self.env.ref('l10n_cl_picking_references.sale_order_form_inherit_reference').id,
        ])

        for view in views:
            view._check_xml()

    def test_delivery_guide_dte_includes_sale_reference(self):
        view = self.env.ref('l10n_cl_edi_stock.dte_subtemplate')

        combined_arch = etree.tostring(view._get_combined_arch(), encoding='unicode')

        self.assertIn('picking.sale_id.client_order_ref', combined_arch)
        self.assertIn('picking.sale_id.date_dte', combined_arch)
