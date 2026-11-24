from lxml import etree

from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestHomologationCrm(TransactionCase):
    """RF-M04 / CA-M03: integración de precotizaciones con CRM y Ventas en Odoo 19."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create({"name": "Cliente CRM"})
        cls.competitor = cls.env["res.partner"].create({
            "name": "Competidor CRM",
            "supplier_rank": 1,
        })
        values = {
            "name": "Producto CRM",
            "list_price": 150.0,
            "standard_price": 60.0,
        }
        if "base_unit_count" in cls.env["product.template"]._fields:
            values["base_unit_count"] = 1
        template = cls.env["product.template"].create(values)
        cls.product = template.product_variant_id
        cls.product.default_code = "CRM-INT-001"
        cls.homologation = cls.env["product.homologation"].create({
            "competitor_id": cls.competitor.id,
            "customer_code": "CRM-EXT-001",
            "customer_description": "Producto solicitado en oportunidad CRM",
            "product_id": cls.product.id,
            "state": "validated",
        })
        cls.lead = cls.env["crm.lead"].create({
            "name": "Oportunidad Homologación Odoo 19",
            "partner_id": cls.customer.id,
            "type": "opportunity",
        })

    def test_01_lead_links_to_homologation_quotes_and_counts(self):
        self.assertEqual(self.lead.homologation_quote_count, 0)
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "lead_id": self.lead.id,
        })
        self.lead.invalidate_recordset(["homologation_quote_count"])
        self.assertEqual(self.lead.homologation_quote_count, 1)
        self.assertIn(quote, self.lead.homologation_quote_ids)

    def test_02_action_open_homologation_quotes_from_lead(self):
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "lead_id": self.lead.id,
        })
        action = self.lead.action_open_homologation_quotes()
        self.assertEqual(action["res_model"], "product.homologation.quote")
        self.assertEqual(action["domain"], [("lead_id", "=", self.lead.id)])
        self.assertEqual(action["context"]["default_lead_id"], self.lead.id)
        self.assertEqual(action["context"]["default_partner_id"], self.customer.id)
        self.assertEqual(action["view_mode"], "list,form")
        found = self.env["product.homologation.quote"].search(action["domain"])
        self.assertIn(quote, found)

    def test_03_convert_quote_with_lead_propagates_to_sale_order(self):
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "lead_id": self.lead.id,
        })
        self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "CRM-EXT-001",
            "customer_description": "Producto solicitado en oportunidad CRM",
            "product_id": self.product.id,
            "homologation_id": self.homologation.id,
            "state": "matched",
            "quantity": 2,
        })
        quote.action_confirm_homologation()
        quote.action_convert_to_sale()

        self.assertEqual(quote.state, "converted")
        self.assertEqual(quote.sale_order_id.homologation_quote_id, quote)
        self.assertEqual(quote.sale_order_id.homologation_lead_id, self.lead)

    def test_04_crm_and_quote_views_render_in_odoo19(self):
        lead_view = self.env.ref("crm.crm_lead_view_form")
        lead_arch = self.env["crm.lead"].get_view(
            view_id=lead_view.id, view_type="form"
        )["arch"]
        lead_root = etree.fromstring(lead_arch.encode())
        self.assertTrue(
            lead_root.xpath("//button[@name='action_open_homologation_quotes']")
        )
        self.assertTrue(lead_root.xpath("//page[@name='homologation']"))

        quote_view = self.env.ref(
            "product_homologation.view_product_homologation_quote_form"
        )
        quote_arch = self.env["product.homologation.quote"].get_view(
            view_id=quote_view.id, view_type="form"
        )["arch"]
        quote_root = etree.fromstring(quote_arch.encode())
        self.assertTrue(quote_root.xpath("//field[@name='lead_id']"))

        form = Form(
            self.env["product.homologation.quote"].with_context(
                default_lead_id=self.lead.id,
                default_partner_id=self.customer.id,
            )
        )
        created_quote = form.save()
        self.assertEqual(created_quote.lead_id, self.lead)
        self.assertEqual(created_quote.partner_id, self.customer)
