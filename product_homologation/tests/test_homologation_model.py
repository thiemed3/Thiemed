from lxml import etree

from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import safe_eval


@tagged("post_install", "-at_install")
class TestHomologationModel(TransactionCase):
    """Pruebas del modelo central product.homologation (V1 migrada a Odoo 19)."""

    def _view_root(self, xmlid):
        view = self.env.ref(xmlid)
        return etree.fromstring(view.arch_db.encode())

    def _create_test_product(self, name, default_code, list_price, standard_price=0.0):
        vals = {
            "name": name,
            "list_price": list_price,
            "standard_price": standard_price,
        }
        if "base_unit_count" in self.env["product.template"]._fields:
            vals["base_unit_count"] = 1

        template = self.env["product.template"].create(vals)
        product = template.product_variant_id
        product.default_code = default_code
        return product

    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create({
            "name": "Xilong Test",
            "supplier_rank": 1,
        })
        self.product = self._create_test_product(
            name="Tijera Metzenbaum 14cm",
            default_code="TZM-001",
            list_price=150.0,
        )
        self.product_b = self._create_test_product(
            name="Tijera Metzenbaum 16cm",
            default_code="TZM-002",
            list_price=180.0,
        )
        self.homologation = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "XIL-SC-001",
            "customer_description": "Scissors curved 14cm",
            "product_id": self.product.id,
            "state": "draft",
        })

    def test_01_create_homologation(self):
        """RF-01: creación básica y valores por defecto."""
        self.assertEqual(self.homologation.state, "draft")
        self.assertTrue(self.homologation.active)
        self.assertEqual(self.homologation.product_default_code, "TZM-001")
        self.assertEqual(self.homologation.product_price, 150.0)

    def test_02_unique_constraint(self):
        """RF-01: no se permiten códigos duplicados por competidor."""
        with self.assertRaises(ValidationError):
            self.env["product.homologation"].create({
                "competitor_id": self.partner.id,
                "customer_code": "XIL-SC-001",
                "customer_description": "Duplicate scissors",
                "product_id": self.product.id,
            })

    def test_03_validation_flow(self):
        """RF-05/RF-06: draft → validated → rejected → draft."""
        self.homologation.action_validate()
        self.assertEqual(self.homologation.state, "validated")
        self.assertTrue(self.homologation.validator_id)
        self.assertTrue(self.homologation.validation_date)

        self.homologation.action_reject()
        self.assertEqual(self.homologation.state, "rejected")

        self.homologation.action_draft()
        self.assertEqual(self.homologation.state, "draft")
        self.assertFalse(self.homologation.validator_id)

    def test_04_normalized_description(self):
        """RF-02: la descripción normalizada se genera al guardar."""
        self.homologation.write({
            "customer_description": "Tijera Curva 14cm - Xilong® (NUEVA)",
        })
        self.assertEqual(
            self.homologation.normalized_description,
            "tijera curva 14cm xilong nueva",
        )

    def test_05_competitor_partner_field(self):
        """RF-03: la marca/competidor es un proveedor."""
        self.assertTrue(self.partner.supplier_rank > 0)
        non_comp = self.env["res.partner"].create({"name": "Clínica Test"})
        self.assertFalse(non_comp.supplier_rank)

    def test_06_cross_homologation_action(self):
        """RF-11: acción de homologaciones cruzadas por producto interno."""
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
        """RF-04: la precisión se almacena."""
        self.homologation.write({"precision_pct": 85.5})
        self.assertEqual(self.homologation.precision_pct, 85.5)

    def test_08_duplicate_detection(self):
        """RF-11: detección de posibles duplicados."""
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
        self.homologation._compute_duplicates()

    def test_09_batch_validate(self):
        """RF-06: validación masiva."""
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
        """RF-01: creación mediante formulario."""
        form = Form(self.env["product.homologation"])
        form.competitor_id = self.partner
        form.customer_code = "FORM-TEST-001"
        form.customer_description = "Form test product"
        form.product_id = self.product
        record = form.save()
        self.assertEqual(record.customer_code, "FORM-TEST-001")
        self.assertEqual(record.product_id, self.product)

    def test_11_optional_competitor_and_code(self):
        """RF-02/RF-03: competidor y código externo son opcionales."""
        record = self.env["product.homologation"].create({
            "customer_description": "Product without customer code",
            "product_id": self.product.id,
        })
        self.assertFalse(record.competitor_id)
        self.assertFalse(record.customer_code)

    def test_12_homologation_level_sets_precision(self):
        """RF-04: el nivel sugiere la precisión esperada."""
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
        """RF-04: la observación se conserva de forma independiente."""
        self.homologation.write({"observation": "10 mm longer than requested"})
        self.assertEqual(self.homologation.observation, "10 mm longer than requested")

    def test_14_action_reject_draft_records_validator(self):
        """RF-06: el rechazo registra al validador."""
        self.homologation.action_reject()

        self.assertEqual(self.homologation.state, "rejected")
        self.assertEqual(self.homologation.validator_id, self.env.user)

    def test_15_batch_reject_server_action(self):
        """RF-06: acción de servidor de rechazo masivo."""
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
        """RF-11: las validadas salen del listado de validación."""
        action = self.env.ref(
            "product_homologation.action_product_homologation_validation"
        )
        self.homologation.action_validate()

        pending = self.env["product.homologation"].search(safe_eval(action.domain))

        self.assertNotIn(self.homologation, pending)

    def test_17_rejected_not_in_validation_action_domain(self):
        """RF-11: las rechazadas salen del listado de validación."""
        action = self.env.ref(
            "product_homologation.action_product_homologation_validation"
        )
        self.homologation.action_reject()

        pending = self.env["product.homologation"].search(safe_eval(action.domain))

        self.assertNotIn(self.homologation, pending)

    def test_18_ph026_homologation_action_uses_normal_views(self):
        """RF-11: el menú usa las vistas normales editables list/form."""
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
        """RF-18: la lista de alternativas solo permite seleccionar."""
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
        """RF-M05: el formulario usa el chatter estándar de Odoo 19."""
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

    def test_21_name_search_matches_code_and_description(self):
        """RF-33: autocompletado por código, descripción y código interno."""
        by_code = self.env["product.homologation"].name_search("XIL-SC")
        self.assertIn(self.homologation.id, [item[0] for item in by_code])

        by_description = self.env["product.homologation"].name_search("curved")
        self.assertIn(self.homologation.id, [item[0] for item in by_description])

        by_internal = self.env["product.homologation"].name_search("TZM-001")
        self.assertIn(self.homologation.id, [item[0] for item in by_internal])

    def test_22_code_suggestions_prioritize_validated(self):
        """RF-33: las sugerencias muestran primero las validadas."""
        validated = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "SUG-100",
            "customer_description": "Sugerencia validada",
            "product_id": self.product.id,
            "state": "validated",
        })
        draft = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "SUG-101",
            "customer_description": "Sugerencia borrador",
            "product_id": self.product_b.id,
            "state": "draft",
        })

        suggestions = self.env["product.homologation"]._get_code_suggestions("SUG-")

        self.assertEqual(suggestions[0], validated)
        self.assertIn(draft, suggestions)

    def test_23_unlink_blocked_for_used_homologations(self):
        """RF-13: no se eliminan homologaciones ya utilizadas."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.partner.id,
        })
        self.homologation.action_validate()
        self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "homologation_id": self.homologation.id,
            "quantity": 1,
        })

        self.assertTrue(self.homologation.is_used)
        self.assertEqual(self.homologation.used_in_quote_count, 1)
        with self.assertRaises(UserError):
            self.homologation.unlink()
        self.assertTrue(self.homologation.exists())

        # La vía correcta es archivar, conservando el histórico.
        self.homologation.action_archive()
        self.assertFalse(self.homologation.active)
        self.assertTrue(self.homologation.exists())

    def test_24_unused_homologation_can_be_deleted(self):
        """RF-12/RF-13: un borrador no utilizado puede eliminarse."""
        draft = self.env["product.homologation"].create({
            "customer_description": "Temporal",
            "product_id": self.product.id,
        })
        draft_id = draft.id
        draft.unlink()
        self.assertFalse(self.env["product.homologation"].browse(draft_id).exists())

    def test_25_priority_validation_rejects_negative(self):
        """RF-23: la prioridad de las reglas debe ser positiva."""
        with self.assertRaises(ValidationError):
            self.env["product.homologation.rule"].create({
                "name": "Regla inválida",
                "rule_type": "lowest_price",
                "priority": -1,
            })

    def test_26_odoo19_manifest_and_list_views(self):
        """RNF-01: el módulo declara Odoo 19 y usa vistas list."""
        module = self.env["ir.module.module"].search(
            [("name", "=", "product_homologation")], limit=1
        )
        self.assertTrue(module.latest_version.startswith("19.0"))

        for xmlid in (
            "product_homologation.view_product_homologation_tree",
            "product_homologation.view_product_homologation_quote_tree",
            "product_homologation.view_product_homologation_rule_tree",
        ):
            root = self._view_root(xmlid)
            self.assertEqual(root.tag, "list")

    def test_27_provisional_state_keeps_origin_quote(self):
        """RF-09: la homologación provisional registra su precotización de origen."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.partner.id,
        })
        line = self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "PROV-MODEL-001",
            "customer_description": "Homologación provisional",
            "product_id": self.product.id,
            "state": "matched",
        })

        self.assertEqual(line.homologation_id.state, "provisional")
        self.assertEqual(line.homologation_id.origin_quote_id, quote)
        self.assertEqual(line.homologation_id.origin_quote_line_id, line)
        self.assertTrue(line.homologation_id.is_provisional)
        self.assertEqual(line.match_status, "provisional")
