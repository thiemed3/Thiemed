from odoo.tests.common import TransactionCase
from odoo.tests import Form


class TestHomologationQuote(TransactionCase):
    """Test the pre-quotation flow."""

    def setUp(self):
        super().setUp()
        # Ensure base_unit_count column has a default (website_sale adds it as required)
        self.env.cr.execute(
            "ALTER TABLE product_template ALTER COLUMN base_unit_count SET DEFAULT 1"
        )
        self.env.cr.execute(
            "ALTER TABLE product_product ALTER COLUMN base_unit_count SET DEFAULT 1"
        )
        self.partner = self.env["res.partner"].create({
            "name": "Cliente CRM",
            "supplier_rank": 1,
        })
        self.customer = self.env["res.partner"].create({
            "name": "Clínica Test",
        })
        self.product = self.env["product.product"].create({
            "name": "Bisturí Eléctrico",
            "default_code": "BIS-001",
            "list_price": 250.0,
        })
        self.homologation = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "CMP-BIS-001",
            "customer_description": "Electric scalpel",
            "product_id": self.product.id,
            "state": "validated",
        })
        self.lead = self.env["crm.lead"].create({
            "name": "Oportunidad Test",
            "partner_id": self.customer.id,
        })

    def test_01_create_quote_from_lead(self):
        """Quote can be created from CRM lead."""
        quote = self.env["product.homologation.quote"].create({
            "lead_id": self.lead.id,
            "partner_id": self.customer.id,
            "name": "PRE-001",
        })
        self.assertEqual(quote.state, "draft")
        self.assertEqual(quote.lead_id, self.lead)

    def test_02_add_line_with_onchange_match(self):
        """Adding a line with known customer_code auto-matches."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-002",
        })
        form = Form(quote)
        with form.line_ids.new() as line:
            line.customer_code = "CMP-BIS-001"
            line.quantity = 5
        quote = form.save()

        line = quote.line_ids[0]
        self.assertEqual(line.product_id, self.product)
        self.assertEqual(line.state, "matched")
        self.assertEqual(line.homologation_id, self.homologation)
        self.assertEqual(line.price_unit, 250.0)

    def test_03_add_line_without_match(self):
        """Unknown codes stay in pending state."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-003",
        })
        form = Form(quote)
        with form.line_ids.new() as line:
            line.customer_code = "UNKN-CODE"
            line.customer_description = "Unknown thingy"
        quote = form.save()

        line = quote.line_ids[0]
        self.assertFalse(line.product_id)
        self.assertEqual(line.state, "pending")

    def test_04_confirm_homologation(self):
        """action_confirm_homologation sets state to homologated."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-004",
        })
        self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "CMP-BIS-001",
            "product_id": self.product.id,
            "state": "matched",
        })
        quote.action_confirm_homologation()
        self.assertEqual(quote.state, "homologated")

    def test_05_convert_to_sale_order(self):
        """Converted quote creates sale.order with traceability."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "lead_id": self.lead.id,
            "name": "PRE-005",
        })
        line = self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "CMP-BIS-001",
            "customer_description": "Electric scalpel",
            "product_id": self.product.id,
            "homologation_id": self.homologation.id,
            "state": "matched",
            "quantity": 3,
            "price_unit": 240.0,
        })
        quote.action_confirm_homologation()
        result = quote.action_convert_to_sale()

        self.assertEqual(quote.state, "converted")
        self.assertTrue(quote.sale_order_id)
        self.assertEqual(result["res_model"], "sale.order")

        so = quote.sale_order_id
        self.assertEqual(so.partner_id, self.customer)
        self.assertEqual(so.opportunity_id, self.lead)
        self.assertEqual(so.origin, quote.name)

        so_line = so.order_line[0]
        self.assertEqual(so_line.product_id, self.product)
        self.assertEqual(so_line.product_uom_qty, 3)
        self.assertEqual(so_line.price_unit, 240.0)
        self.assertEqual(so_line.homologation_customer_code, "CMP-BIS-001")
        self.assertEqual(so_line.homologation_customer_description, "Electric scalpel")
        self.assertEqual(so_line.homologation_quote_line_id, line)

    def test_06_quote_line_price_from_product(self):
        """Price is auto-set from product list_price via compute."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-006",
        })
        form = Form(quote)
        with form.line_ids.new() as line:
            line.product_id = self.product
        quote = form.save()
        self.assertEqual(quote.line_ids[0].price_unit, 250.0)

    def test_07_crm_lead_smart_button(self):
        """CRM lead shows homologation quote count and action."""
        self.env["product.homologation.quote"].create({
            "lead_id": self.lead.id,
            "partner_id": self.customer.id,
            "name": "PRE-007",
        })
        self.lead._compute_homologation_quote_count()
        self.assertEqual(self.lead.homologation_quote_count, 1)

        action = self.lead.action_open_homologation_quotes()
        self.assertEqual(action["res_model"], "product.homologation.quote")

    def test_08_form_ui_quote_with_lines(self):
        """Full UI simulation: create quote, add lines, convert to SO."""
        quote_form = Form(self.env["product.homologation.quote"])
        quote_form.partner_id = self.customer
        with quote_form.line_ids.new() as line:
            line.customer_code = "CMP-BIS-001"
            line.quantity = 2
        quote = quote_form.save()

        self.assertEqual(len(quote.line_ids), 1)
        self.assertEqual(quote.line_ids[0].state, "matched")

        quote.action_confirm_homologation()
        self.assertEqual(quote.state, "homologated")

        result = quote.action_convert_to_sale()
        self.assertEqual(quote.state, "converted")
        self.assertTrue(quote.sale_order_id)

    def test_09_cancel_quote(self):
        """Quote can be cancelled from any non-converted state."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-009",
            "state": "homologated",
        })
        quote.action_cancel()
        self.assertEqual(quote.state, "cancelled")
