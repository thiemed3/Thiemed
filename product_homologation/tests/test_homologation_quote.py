from odoo.tests.common import TransactionCase
from odoo.tests import Form
from odoo.exceptions import UserError


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
        self.product_b = self.env["product.product"].create({
            "name": "Bisturí Alternativo",
            "default_code": "BIS-002",
            "list_price": 300.0,
        })
        self.env["product.supplierinfo"].create({
            "partner_id": self.partner.id,
            "product_tmpl_id": self.product.product_tmpl_id.id,
            "min_qty": 1.0,
            "price": 100.0,
            "delay": 1,
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

    def _transient_line_for_code(self, code):
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-TRANSIENT",
        })
        line = self.env["product.homologation.quote.line"].new({
            "quote_id": quote.id,
            "customer_code": code,
            "customer_description": "Transient description",
        })
        line._onchange_customer_code()
        return line

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
        """Unknown codes are marked as unmatched after lookup."""
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
        self.assertEqual(line.state, "unmatched")

    def test_04_confirm_homologation(self):
        """action_confirm_homologation sets state to homologated."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-004",
        })
        self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "CMP-BIS-001",
            "customer_description": "Electric scalpel",
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
            line.customer_description = "Manual product line"
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

    def test_10_case_insensitive_code_match(self):
        """Customer code lookup is case-insensitive and trims edges."""
        line = self._transient_line_for_code("  cmp-bis-001  ")
        self.assertEqual(line.product_id, self.product)
        self.assertEqual(line.homologation_id, self.homologation)
        self.assertEqual(line.state, "matched")

    def test_11_multiple_validated_codes_do_not_auto_select(self):
        """Multiple validated homologations do not pick one arbitrarily."""
        other_partner = self.env["res.partner"].create({
            "name": "Otro Competidor",
            "supplier_rank": 1,
        })
        other_homologation = self.env["product.homologation"].create({
            "competitor_id": other_partner.id,
            "customer_code": "CMP-BIS-001",
            "customer_description": "Alternative scalpel",
            "product_id": self.product_b.id,
            "state": "validated",
        })

        line = self._transient_line_for_code("CMP-BIS-001")

        self.assertFalse(line.product_id)
        self.assertFalse(line.homologation_id)
        self.assertEqual(line.state, "unmatched")
        self.assertEqual(
            set(line.possible_homologation_ids.ids),
            {self.homologation.id, other_homologation.id},
        )

    def test_12_draft_homologation_is_not_auto_matched(self):
        """Draft homologations are detected but not used as automatic matches."""
        self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "DRAFT-CODE",
            "customer_description": "Draft scalpel",
            "product_id": self.product.id,
            "state": "draft",
        })

        line = self._transient_line_for_code("DRAFT-CODE")

        self.assertFalse(line.product_id)
        self.assertFalse(line.homologation_id)
        self.assertEqual(line.state, "unmatched")
        self.assertEqual(line.match_status, "draft")

    def test_13_rejected_homologation_is_not_auto_matched(self):
        """Rejected homologations are never used automatically."""
        self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "REJECT-CODE",
            "customer_description": "Rejected scalpel",
            "product_id": self.product.id,
            "state": "rejected",
        })

        line = self._transient_line_for_code("REJECT-CODE")

        self.assertFalse(line.product_id)
        self.assertFalse(line.homologation_id)
        self.assertEqual(line.state, "unmatched")
        self.assertEqual(line.match_status, "rejected")

    def test_14_confirm_blocks_pending_lines(self):
        """Homologar todo blocks incomplete quote lines."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-PENDING-CONFIRM",
        })
        self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "PENDING-CODE",
            "customer_description": "Pending product",
            "state": "pending",
        })

        with self.assertRaises(UserError):
            quote.action_confirm_homologation()
        self.assertEqual(quote.state, "draft")

    def test_15_convert_blocks_pending_lines(self):
        """Conversion blocks incomplete quote lines and creates no sale order."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-PENDING-CONVERT",
            "state": "homologated",
        })
        self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "PENDING-CODE",
            "customer_description": "Pending product",
            "state": "pending",
        })
        before_count = self.env["sale.order"].search_count([("origin", "=", quote.name)])

        with self.assertRaises(UserError):
            quote.action_convert_to_sale()

        after_count = self.env["sale.order"].search_count([("origin", "=", quote.name)])
        self.assertEqual(before_count, after_count)

    def test_16_reconversion_is_blocked(self):
        """A converted quote cannot create a second sale order."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-DOUBLE-CONVERT",
        })
        self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "CMP-BIS-001",
            "customer_description": "Electric scalpel",
            "product_id": self.product.id,
            "homologation_id": self.homologation.id,
            "state": "matched",
        })
        quote.action_confirm_homologation()
        quote.action_convert_to_sale()
        before_count = self.env["sale.order"].search_count([("origin", "=", quote.name)])

        with self.assertRaises(UserError):
            quote.action_convert_to_sale()

        after_count = self.env["sale.order"].search_count([("origin", "=", quote.name)])
        self.assertEqual(before_count, after_count)

    def test_17_create_homologation_without_competitor_does_not_use_supplier(self):
        """Automatic draft homologation does not infer competitor from product supplier."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-NO-COMPETITOR",
        })
        line = self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "NEW-NO-COMP",
            "customer_description": "New product without competitor",
            "product_id": self.product.id,
            "state": "matched",
        })

        self.assertTrue(line.homologation_id)
        self.assertEqual(line.homologation_id.state, "draft")
        self.assertFalse(line.homologation_id.competitor_id)

    def test_18_select_validated_alternative(self):
        """User can choose one validated alternative when code has several."""
        other_partner = self.env["res.partner"].create({
            "name": "Competidor Alternativo",
            "supplier_rank": 1,
        })
        other_homologation = self.env["product.homologation"].create({
            "competitor_id": other_partner.id,
            "customer_code": "CMP-BIS-001",
            "customer_description": "Alternative scalpel",
            "product_id": self.product_b.id,
            "state": "validated",
            "homologation_level": "near",
        })

        line = self._transient_line_for_code("CMP-BIS-001")
        action = line.action_open_possible_homologations()
        self.assertEqual(action["res_model"], "product.homologation")
        self.assertEqual(
            set(action["domain"][0][2]),
            {self.homologation.id, other_homologation.id},
        )

        line.homologation_id = other_homologation
        line._onchange_homologation_id()

        self.assertEqual(line.product_id, self.product_b)
        self.assertEqual(line.homologation_id, other_homologation)
        self.assertEqual(line.homologation_level, "near")
        self.assertEqual(line.homologation_precision_pct, 90.0)
        self.assertEqual(line.state, "matched")
        self.assertEqual(line.match_status, "validated")

    def test_19_code_empty_description_does_not_match_by_description(self):
        """Description-only lines are allowed but do not trigger automatic matching."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-DESC-ONLY",
        })
        line = self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_description": "Electric scalpel",
        })

        self.assertFalse(line.customer_code)
        self.assertFalse(line.product_id)
        self.assertFalse(line.homologation_id)
        self.assertEqual(line.state, "pending")
        self.assertEqual(line.match_status, "pending")

    def test_20_description_is_required_on_quote_line(self):
        """Customer description is required on quote lines."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-NO-DESC",
        })

        with self.assertRaises(Exception):
            self.env["product.homologation.quote.line"].create({
                "quote_id": quote.id,
                "customer_code": "NO-DESC",
            })

    def test_21_quote_line_price_updates_when_product_changes(self):
        """Unit price follows product list price when product_id changes."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-PRICE-CHANGE",
        })
        line = self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_description": "Manual product line",
            "product_id": self.product.id,
        })
        self.assertEqual(line.price_unit, 250.0)

        line.write({"product_id": self.product_b.id})
        self.assertEqual(line.price_unit, 300.0)

    def test_22_observations_trace_to_sale_order(self):
        """Homologation and quote observations are preserved on conversion."""
        self.homologation.write({
            "observation": "10 mm longer than requested",
            "homologation_level": "near",
        })
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-OBS-CONVERT",
        })
        line = self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "homologation_id": self.homologation.id,
            "quantity": 2,
            "observation": "Quote-specific note",
        })

        self.assertEqual(line.homologation_observation, "10 mm longer than requested")
        quote.action_confirm_homologation()
        quote.action_convert_to_sale()

        so_line = quote.sale_order_id.order_line[0]
        self.assertEqual(so_line.homologation_observation, "10 mm longer than requested")
        self.assertEqual(so_line.homologation_quote_observation, "Quote-specific note")
        self.assertEqual(so_line.homologation_level, "near")
        self.assertEqual(so_line.homologation_precision_pct, 90.0)
        self.assertIn("Obs. homologación: 10 mm longer than requested", so_line.name)
        self.assertIn("Obs. precotización: Quote-specific note", so_line.name)

    def test_23_draft_homologation_is_not_counted_as_validated(self):
        """PH-021-A: draft homologations are not counted as approved."""
        draft_homologation = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "DRAFT-MANUAL-PRODUCT",
            "customer_description": "Draft manual product",
            "product_id": self.product.id,
            "state": "draft",
        })
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-DRAFT-COUNT",
        })
        line = self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "DRAFT-MANUAL-PRODUCT",
            "customer_description": "Draft manual product",
            "product_id": self.product.id,
            "homologation_id": draft_homologation.id,
            "state": "matched",
        })

        self.assertEqual(line.match_status, "draft")
        self.assertEqual(quote.matched_count, 0)
        self.assertEqual(
            dict(line._fields["state"].selection)["matched"],
            "Producto asignado",
        )

    def test_24_validated_homologation_is_counted(self):
        """PH-021-B: validated homologations count as homologated."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-VALIDATED-COUNT",
        })
        line = self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "homologation_id": self.homologation.id,
        })

        self.assertEqual(line.match_status, "validated")
        self.assertEqual(line.state, "matched")
        self.assertEqual(quote.matched_count, 1)

    def test_25_rejected_homologation_is_not_counted_as_validated(self):
        """PH-021-C: rejected homologations are not shown as approved."""
        rejected_homologation = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "REJECTED-MANUAL-PRODUCT",
            "customer_description": "Rejected manual product",
            "product_id": self.product.id,
            "state": "rejected",
        })
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-REJECTED-COUNT",
        })
        line = self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "REJECTED-MANUAL-PRODUCT",
            "customer_description": "Rejected manual product",
            "product_id": self.product.id,
            "homologation_id": rejected_homologation.id,
            "state": "matched",
        })

        self.assertEqual(line.match_status, "rejected")
        self.assertEqual(quote.matched_count, 0)

    def test_26_matched_count_uses_validated_homologations_only(self):
        """PH-021-D: Homologadas counts only approved homologations."""
        draft_homologation = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "MIX-DRAFT",
            "customer_description": "Mixed draft product",
            "product_id": self.product.id,
            "state": "draft",
        })
        rejected_homologation = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "MIX-REJECTED",
            "customer_description": "Mixed rejected product",
            "product_id": self.product_b.id,
            "state": "rejected",
        })
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-MIXED-COUNT",
        })
        self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "homologation_id": self.homologation.id,
        })
        self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "MIX-DRAFT",
            "customer_description": "Mixed draft product",
            "product_id": self.product.id,
            "homologation_id": draft_homologation.id,
            "state": "matched",
        })
        self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "MIX-REJECTED",
            "customer_description": "Mixed rejected product",
            "product_id": self.product_b.id,
            "homologation_id": rejected_homologation.id,
            "state": "matched",
        })
        self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_description": "Product without validated homologation",
            "product_id": self.product_b.id,
            "state": "matched",
        })

        self.assertEqual(quote.line_count, 4)
        self.assertEqual(quote.matched_count, 1)

    def test_27_ph022_single_validation_reconciles_existing_quote_line(self):
        """PH-022-A: validating the only applicable draft reconciles the line."""
        draft_homologation = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "PH022-A-ONLY-VALIDATE-TEST",
            "customer_description": "Validated after quote line creation",
            "product_id": self.product.id,
            "state": "draft",
        })
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PC-00013",
        })
        line = self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "PH022-A-ONLY-VALIDATE-TEST",
            "customer_description": "Original quote line description",
            "state": "unmatched",
        })

        self.assertEqual(line.match_status, "draft")
        self.assertEqual(quote.matched_count, 0)

        draft_homologation.action_validate()

        self.assertEqual(line.homologation_id, draft_homologation)
        self.assertEqual(line.product_id, self.product)
        self.assertEqual(line.customer_description, "Validated after quote line creation")
        self.assertEqual(line.state, "matched")
        self.assertEqual(line.match_status, "validated")
        self.assertFalse(line.possible_homologation_ids)
        self.assertEqual(quote.matched_count, 1)
        quote.action_confirm_homologation()
        self.assertEqual(quote.state, "homologated")

    def test_28_ph022_multiple_validated_do_not_reconcile_automatically(self):
        """PH-022-B: multiple validated alternatives keep the line unresolved."""
        other_partner = self.env["res.partner"].create({
            "name": "PH-022 Alternative Competitor",
            "supplier_rank": 1,
        })
        first_homologation = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "PH022-B-MULTI-VALIDATE-TEST",
            "customer_description": "First alternative",
            "product_id": self.product.id,
            "state": "draft",
        })
        second_homologation = self.env["product.homologation"].create({
            "competitor_id": other_partner.id,
            "customer_code": "PH022-B-MULTI-VALIDATE-TEST",
            "customer_description": "Second alternative",
            "product_id": self.product_b.id,
            "state": "draft",
        })
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-PH022-MULTI",
        })
        line = self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "PH022-B-MULTI-VALIDATE-TEST",
            "customer_description": "Ambiguous quote line",
            "state": "unmatched",
        })

        (first_homologation | second_homologation).action_validate()

        self.assertFalse(line.homologation_id)
        self.assertFalse(line.product_id)
        self.assertEqual(line.state, "unmatched")
        self.assertEqual(line.match_status, "alternatives")
        self.assertEqual(line.possible_homologation_count, 2)
        self.assertEqual(
            set(line.possible_homologation_ids.ids),
            {first_homologation.id, second_homologation.id},
        )
        self.assertEqual(quote.matched_count, 0)

    def test_29_ph022_rejected_homologation_never_reconciles_line(self):
        """PH-022-C: rejected homologations do not become valid matches."""
        draft_homologation = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "PH022-C-REJECTED-TEST",
            "customer_description": "Rejected after quote line creation",
            "product_id": self.product.id,
            "state": "draft",
        })
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-PH022-REJECTED",
        })
        line = self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "PH022-C-REJECTED-TEST",
            "customer_description": "Rejected quote line",
            "state": "unmatched",
        })

        draft_homologation.action_reject()

        self.assertFalse(line.homologation_id)
        self.assertFalse(line.product_id)
        self.assertEqual(line.state, "unmatched")
        self.assertEqual(line.match_status, "rejected")
        self.assertFalse(line.possible_homologation_ids)
        self.assertEqual(quote.matched_count, 0)
