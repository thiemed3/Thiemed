from lxml import etree

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError
from odoo.tests import Form
from odoo.tools.safe_eval import safe_eval


class TestHomologationModel(TransactionCase):
    """Test the core product.homologation model."""

    def _view_root(self, xmlid):
        view = self.env.ref(xmlid)
        return etree.fromstring(view.arch_db.encode())

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
            "name": "Xilong Test",
            "supplier_rank": 1,
        })
        self.product = self.env["product.product"].create({
            "name": "Tijera Metzenbaum 14cm",
            "default_code": "TZM-001",
            "list_price": 150.0,
        })
        self.product_b = self.env["product.product"].create({
            "name": "Tijera Metzenbaum 16cm",
            "default_code": "TZM-002",
            "list_price": 180.0,
        })
        self.homologation = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "XIL-SC-001",
            "customer_description": "Scissors curved 14cm",
            "product_id": self.product.id,
            "state": "draft",
        })

    def test_01_create_homologation(self):
        """Verify basic creation and field defaults."""
        self.assertEqual(self.homologation.state, "draft")
        self.assertTrue(self.homologation.active)
        self.assertEqual(self.homologation.product_default_code, "TZM-001")

    def test_02_unique_constraint(self):
        """Duplicate competitor+code should raise."""
        with self.assertRaises(Exception):
            self.env["product.homologation"].create({
                "competitor_id": self.partner.id,
                "customer_code": "XIL-SC-001",
                "customer_description": "Duplicate scissors",
                "product_id": self.product.id,
            })

    def test_03_validation_flow(self):
        """draft → validated → rejected → draft."""
        self.homologation.action_validate()
        self.assertEqual(self.homologation.state, "validated")
        self.assertTrue(self.homologation.validator_id)

        self.homologation.action_reject()
        self.assertEqual(self.homologation.state, "rejected")

        self.homologation.action_draft()
        self.assertEqual(self.homologation.state, "draft")
        self.assertFalse(self.homologation.validator_id)

    def test_04_normalized_description(self):
        """normalized_description is generated on save."""
        self.homologation.write({
            "customer_description": "Tijera Curva 14cm - Xilong® (NUEVA)",
        })
        self.assertEqual(
            self.homologation.normalized_description,
            "tijera curva 14cm xilong nueva",
        )

    def test_05_competitor_partner_field(self):
        """Verify supplier_rank flag on partner."""
        self.assertTrue(self.partner.supplier_rank > 0)
        non_comp = self.env["res.partner"].create({"name": "Clínica Test"})
        self.assertFalse(non_comp.supplier_rank)

    def test_06_cross_homologation_action(self):
        """action_find_cross_homologations returns window action."""
        self.homologation.action_validate()
        h2 = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "XIL-SC-002",
            "customer_description": "Second scissors",
            "product_id": self.product.id,
            "state": "validated",
        })
        action = h2.action_find_cross_homologations()
        self.assertEqual(action["res_model"], "product.homologation")
        self.assertIn(self.homologation.id, action["domain"][0][2])

    def test_07_precision_pct_stored(self):
        """Precision percentage is stored correctly."""
        self.homologation.write({"precision_pct": 85.5})
        self.assertEqual(self.homologation.precision_pct, 85.5)

    def test_08_duplicate_detection(self):
        """duplicate_homologation_ids finds potential duplicates."""
        self.homologation.action_validate()
        other_partner = self.env["res.partner"].create({
            "name": "Other Competitor",
            "supplier_rank": 1,
        })
        dup = self.env["product.homologation"].create({
            "competitor_id": other_partner.id,
            "customer_code": "OTHER-001",
            "customer_description": "Other competitor product",
            "product_id": self.product_b.id,
        })
        dup._compute_duplicates()

    def test_09_batch_validate(self):
        """Server action validates multiple at once."""
        h2 = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "XIL-SC-099",
            "customer_description": "Batch validate product",
            "product_id": self.product.id,
            "state": "draft",
        })
        (self.homologation | h2).action_validate()
        self.assertEqual(self.homologation.state, "validated")
        self.assertEqual(h2.state, "validated")

    def test_10_form_ui_create_homologation(self):
        """Simulate UI creation via Form."""
        form = Form(self.env["product.homologation"])
        form.competitor_id = self.partner
        form.customer_code = "FORM-TEST-001"
        form.customer_description = "Form test product"
        form.product_id = self.product
        record = form.save()
        self.assertEqual(record.customer_code, "FORM-TEST-001")
        self.assertEqual(record.product_id, self.product)

    def test_11_optional_competitor_and_code(self):
        """Competitor and customer code are optional in V1."""
        record = self.env["product.homologation"].create({
            "customer_description": "Product without customer code",
            "product_id": self.product.id,
        })
        self.assertFalse(record.competitor_id)
        self.assertFalse(record.customer_code)

    def test_12_homologation_level_sets_precision(self):
        """Manual homologation level suggests the expected precision."""
        exact = self.env["product.homologation"].create({
            "customer_description": "Exact product",
            "product_id": self.product.id,
            "homologation_level": "exact",
        })
        near = self.env["product.homologation"].create({
            "customer_description": "Near product",
            "product_id": self.product_b.id,
            "homologation_level": "near",
        })

        self.assertEqual(exact.precision_pct, 100.0)
        self.assertEqual(near.precision_pct, 90.0)

        near.write({"homologation_level": "approximate"})
        self.assertEqual(near.precision_pct, 80.0)

    def test_13_observation_is_preserved(self):
        """Homologation observation remains stored independently."""
        self.homologation.write({"observation": "10 mm longer than requested"})
        self.assertEqual(self.homologation.observation, "10 mm longer than requested")

    def test_14_action_reject_draft_records_validator(self):
        """PH-020-A: draft homologation can be rejected by a validator."""
        self.homologation.action_reject()

        self.assertEqual(self.homologation.state, "rejected")
        self.assertEqual(self.homologation.validator_id, self.env.user)

    def test_15_batch_reject_server_action(self):
        """PH-020-B: server action rejects multiple draft homologations."""
        h2 = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "XIL-SC-REJ-002",
            "customer_description": "Batch reject product",
            "product_id": self.product_b.id,
            "state": "draft",
        })
        action = self.env.ref(
            "product_homologation.action_product_homologation_batch_reject"
        )

        action.with_context(
            active_model="product.homologation",
            active_id=self.homologation.id,
            active_ids=(self.homologation | h2).ids,
        ).run()

        self.assertEqual(self.homologation.state, "rejected")
        self.assertEqual(h2.state, "rejected")
        self.assertEqual(self.homologation.validator_id, self.env.user)
        self.assertEqual(h2.validator_id, self.env.user)

    def test_16_validated_not_in_validation_action_domain(self):
        """PH-020-C: validated records leave the validation worklist."""
        action = self.env.ref(
            "product_homologation.action_product_homologation_validation"
        )
        self.homologation.action_validate()

        pending = self.env["product.homologation"].search(safe_eval(action.domain))

        self.assertNotIn(self.homologation, pending)

    def test_17_rejected_not_in_validation_action_domain(self):
        """PH-020-D: rejected records leave the validation worklist."""
        action = self.env.ref(
            "product_homologation.action_product_homologation_validation"
        )
        self.homologation.action_reject()

        pending = self.env["product.homologation"].search(safe_eval(action.domain))

        self.assertNotIn(self.homologation, pending)

    def test_18_ph026_homologation_action_uses_normal_views(self):
        """PH-026-A/B/C: menu action uses the editable normal list/form views."""
        action = self.env.ref("product_homologation.action_product_homologation")
        normal_tree = self.env.ref("product_homologation.view_product_homologation_tree")
        normal_form = self.env.ref("product_homologation.view_product_homologation_form")
        possible_tree = self.env.ref(
            "product_homologation.view_product_homologation_possible_tree"
        )
        action_views = action.view_ids.sorted("sequence")

        self.assertEqual(action.view_mode, "list,form")
        self.assertEqual(action_views[0].view_mode, "list")
        self.assertEqual(action_views[0].view_id, normal_tree)
        self.assertEqual(action_views[1].view_mode, "form")
        self.assertEqual(action_views[1].view_id, normal_form)
        self.assertNotIn(possible_tree, action_views.mapped("view_id"))

        tree_root = self._view_root("product_homologation.view_product_homologation_tree")
        self.assertEqual(tree_root.tag, "list")
        self.assertNotIn(tree_root.get("create"), ("0", "false", "False"))

    def test_19_ph026_possible_tree_remains_readonly_selection_view(self):
        """PH-026-D: alternatives list stays limited to explicit selection."""
        tree_root = self._view_root(
            "product_homologation.view_product_homologation_possible_tree"
        )

        self.assertEqual(tree_root.get("create"), "0")
        self.assertEqual(tree_root.get("edit"), "0")
        self.assertEqual(tree_root.get("delete"), "0")
        self.assertTrue(
            tree_root.xpath("//button[@name='action_apply_to_quote_line']")
        )

    def test_20_ph027_normal_form_uses_standard_chatter(self):
        """PH-027: normal form uses Odoo 18 chatter component, not technical fields."""
        form_view = self.env.ref("product_homologation.view_product_homologation_form")
        form_arch = self.env["product.homologation"].get_view(
            view_id=form_view.id,
            view_type="form",
        )["arch"]
        form_root = etree.fromstring(form_arch.encode())

        self.assertTrue(form_root.xpath("//chatter"))
        self.assertFalse(form_root.xpath("//div[contains(@class, 'oe_chatter')]"))
        self.assertFalse(form_root.xpath("//field[@name='message_follower_ids']"))
        self.assertFalse(form_root.xpath("//field[@name='activity_ids']"))
        self.assertFalse(form_root.xpath("//field[@name='message_ids']"))
