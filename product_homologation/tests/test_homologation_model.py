from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError
from odoo.tests import Form


class TestHomologationModel(TransactionCase):
    """Test the core product.homologation model."""

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
            "competitor": True,
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
        """Verify competitor flag on partner."""
        self.assertTrue(self.partner.competitor)
        non_comp = self.env["res.partner"].create({"name": "Clínica Test"})
        self.assertFalse(non_comp.competitor)

    def test_06_cross_homologation_action(self):
        """action_find_cross_homologations returns window action."""
        self.homologation.action_validate()
        h2 = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "XIL-SC-002",
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
            "competitor": True,
        })
        dup = self.env["product.homologation"].create({
            "competitor_id": other_partner.id,
            "customer_code": "OTHER-001",
            "product_id": self.product_b.id,
        })
        dup._compute_duplicates()

    def test_09_batch_validate(self):
        """Server action validates multiple at once."""
        h2 = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "XIL-SC-099",
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
