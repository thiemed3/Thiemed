from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase

SELLER_GROUP = "product_homologation.group_homologation_seller"
SPECIALIST_GROUP = "product_homologation.group_homologation_specialist"


class HomologationTestBase(TransactionCase):
    """Utilidades comunes para las pruebas de la V2 en Odoo 19."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.competitor = cls.env["res.partner"].create({
            "name": "Competidor V2",
            "supplier_rank": 1,
        })
        cls.other_competitor = cls.env["res.partner"].create({
            "name": "Competidor Alternativo V2",
            "supplier_rank": 1,
        })
        cls.customer = cls.env["res.partner"].create({"name": "Cliente V2"})
        cls.product = cls._create_product("Producto V2 A", "V2-A", 100.0, 40.0)
        cls.product_b = cls._create_product("Producto V2 B", "V2-B", 80.0, 30.0)
        cls.product_c = cls._create_product("Producto V2 C", "V2-C", 120.0, 50.0)

    @classmethod
    def _create_product(cls, name, code, list_price, standard_price=0.0):
        values = {
            "name": name,
            "list_price": list_price,
            "standard_price": standard_price,
        }
        if "base_unit_count" in cls.env["product.template"]._fields:
            values["base_unit_count"] = 1
        template = cls.env["product.template"].create(values)
        product = template.product_variant_id
        product.default_code = code
        return product

    def _create_homologation(self, code, product, state="validated", **extra):
        values = {
            "competitor_id": (extra.pop("competitor_id", self.competitor)).id,
            "customer_code": code,
            "customer_description": extra.pop(
                "customer_description", "Descripción %s" % code
            ),
            "product_id": product.id,
            "state": state,
        }
        values.update(extra)
        return self.env["product.homologation"].create(values)

    def _create_quote(self, name=None):
        values = {"partner_id": self.customer.id}
        if name:
            values["name"] = name
        return self.env["product.homologation.quote"].create(values)

    def _add_line(self, quote, code, product=None, **extra):
        values = {
            "quote_id": quote.id,
            "customer_code": code,
            "customer_description": extra.pop(
                "customer_description", "Línea %s" % code
            ),
        }
        if product is not None:
            values["product_id"] = product.id
        values.update(extra)
        return self.env["product.homologation.quote.line"].create(values)


@tagged("post_install", "-at_install")
class TestProvisionalFlow(HomologationTestBase):
    """RF-08, RF-09, RF-10: homologaciones provisionales."""

    def test_01_line_creates_provisional_homologation(self):
        quote = self._create_quote("V2-PROV-01")
        line = self._add_line(quote, "PROV-001", self.product)

        self.assertTrue(line.homologation_id)
        self.assertEqual(line.homologation_id.state, "provisional")
        self.assertTrue(line.homologation_id.is_provisional)
        self.assertEqual(line.homologation_id.origin_quote_id, quote)
        self.assertEqual(line.homologation_id.origin_quote_line_id, line)
        self.assertEqual(line.state, "matched")
        self.assertEqual(line.match_status, "provisional")
        self.assertEqual(quote.provisional_count, 1)
        self.assertEqual(quote.matched_count, 0)

    def test_02_provisional_is_usable_in_origin_quote(self):
        quote = self._create_quote("V2-PROV-02")
        first = self._add_line(quote, "PROV-002", self.product)
        second = self._add_line(quote, "PROV-002", self.product)

        self.assertEqual(second.homologation_id, first.homologation_id)
        self.assertEqual(second.state, "matched")
        self.assertEqual(second.match_status, "provisional")

    def test_03_provisional_is_not_usable_in_another_quote(self):
        origin = self._create_quote("V2-PROV-03-A")
        self._add_line(origin, "PROV-003", self.product)
        other = self._create_quote("V2-PROV-03-B")
        line = self._add_line(other, "PROV-003", self.product)

        self.assertFalse(line.homologation_id)
        self.assertNotEqual(line.match_status, "provisional")
        self.assertEqual(
            self.env["product.homologation"].search_count([
                ("customer_code", "=ilike", "PROV-003"),
                ("state", "=", "provisional"),
            ]),
            1,
        )

    def test_04_homologar_todo_accepts_provisional_lines(self):
        quote = self._create_quote("V2-PROV-04")
        self._add_line(quote, "PROV-004", self.product)

        quote.action_confirm_homologation()

        self.assertEqual(quote.state, "homologated")
        self.assertEqual(quote.provisional_count, 1)

    def test_05_conversion_blocks_provisional_until_validated(self):
        quote = self._create_quote("V2-PROV-05")
        line = self._add_line(quote, "PROV-005", self.product, quantity=2)
        quote.action_confirm_homologation()

        with self.assertRaises(UserError):
            quote.action_convert_to_sale()
        self.assertEqual(
            self.env["sale.order"].search_count([("origin", "=", quote.name)]), 0
        )

        line.homologation_id.action_validate()

        self.assertEqual(line.match_status, "validated")
        self.assertEqual(quote.matched_count, 1)
        quote.action_convert_to_sale()
        self.assertEqual(quote.state, "converted")
        self.assertEqual(
            quote.sale_order_id.order_line.homologation_id, line.homologation_id
        )

    def test_06_send_to_validation_sets_provisional_state(self):
        homologation = self._create_homologation(
            "PROV-006", self.product, state="draft"
        )

        homologation.action_send_to_validation()

        self.assertEqual(homologation.state, "provisional")
        self.assertTrue(homologation.is_provisional)

    def test_07_validated_homologation_is_not_provisional(self):
        homologation = self._create_homologation("PROV-007", self.product)
        self.assertFalse(homologation.is_provisional)


@tagged("post_install", "-at_install")
class TestAlternativesWizard(HomologationTestBase):
    """RF-21, RF-22, RF-25: ventana emergente simplificada de alternativas."""

    def setUp(self):
        super().setUp()
        self.env["product.homologation.rule"].search([]).write({"active": False})
        self.env["product.homologation.rule"].create({
            "name": "V2 - Mayor precisión",
            "rule_type": "highest_precision",
            "priority": 10,
        })
        self.high_precision = self._create_homologation(
            "WIZ-001",
            self.product,
            precision_pct=100.0,
            observation="Alternativa exacta",
        )
        self.low_precision = self._create_homologation(
            "WIZ-001",
            self.product_b,
            competitor_id=self.other_competitor,
            precision_pct=80.0,
            homologation_level="approximate",
        )
        self.quote = self._create_quote("V2-WIZ-01")
        self.line = self._add_line(self.quote, "WIZ-001")

    def _open_wizard(self):
        self.assertTrue(self.line.can_open_possible_homologations)
        action = self.line.action_open_alternatives_wizard()
        wizard = self.env["product.homologation.alternatives.wizard"].browse(
            action["res_id"]
        )
        return action, wizard

    def test_01_wizard_lists_candidates_with_required_data(self):
        action, wizard = self._open_wizard()

        self.assertEqual(action["res_model"], "product.homologation.alternatives.wizard")
        self.assertEqual(action["target"], "new")
        self.assertEqual(len(wizard.candidate_ids), 2)
        self.assertEqual(wizard.customer_code, "WIZ-001")

        candidate = wizard.candidate_ids.filtered(
            lambda item: item.homologation_id == self.high_precision
        )
        self.assertEqual(candidate.reference, "WIZ-001")
        self.assertEqual(candidate.description, "Descripción WIZ-001")
        self.assertEqual(candidate.price, 100.0)
        self.assertEqual(candidate.brand_id, self.competitor)
        self.assertEqual(candidate.precision_pct, 100.0)
        self.assertTrue(candidate.recommended)
        self.assertFalse(candidate.is_selected)

    def test_02_wizard_marks_recommended_alternative(self):
        _action, wizard = self._open_wizard()

        self.assertEqual(wizard.recommended_id, self.high_precision)
        self.assertEqual(wizard.recommendation_reason, "V2 - Mayor precisión")
        self.assertEqual(
            wizard.candidate_ids.filtered("recommended").homologation_id,
            self.high_precision,
        )

    def test_03_candidate_selection_applies_homologation(self):
        _action, wizard = self._open_wizard()
        candidate = wizard.candidate_ids.filtered(
            lambda item: item.homologation_id == self.low_precision
        )

        result = candidate.action_select()

        self.assertEqual(result["res_model"], "product.homologation.quote")
        self.assertEqual(result["res_id"], self.quote.id)
        self.assertEqual(self.line.homologation_id, self.low_precision)
        self.assertEqual(self.line.product_id, self.product_b)
        self.assertEqual(self.line.state, "matched")
        self.assertEqual(self.line.match_status, "validated")
        self.assertEqual(self.line.possible_homologation_count, 2)

    def test_04_apply_recommended_from_wizard(self):
        _action, wizard = self._open_wizard()

        result = wizard.action_apply_recommended()

        self.assertEqual(result["res_id"], self.quote.id)
        self.assertEqual(self.line.homologation_id, self.high_precision)
        self.assertEqual(self.line.product_id, self.product)

    def test_05_apply_recommended_from_line(self):
        result = self.line.action_apply_recommended()

        self.assertEqual(result["res_id"], self.quote.id)
        self.assertEqual(self.line.homologation_id, self.high_precision)
        self.assertEqual(self.line.match_status, "validated")

    def test_06_wizard_close_returns_close_action(self):
        _action, wizard = self._open_wizard()
        self.assertEqual(
            wizard.action_close(), {"type": "ir.actions.act_window_close"}
        )

    def test_07_transient_line_cannot_open_wizard(self):
        transient = self.env["product.homologation.quote.line"].new({
            "quote_id": self.quote.id,
            "customer_code": "WIZ-001",
            "customer_description": "Transient",
        })
        transient._onchange_customer_code()

        self.assertFalse(transient.can_open_possible_homologations)
        self.assertEqual(transient.possible_homologation_count, 2)


@tagged("post_install", "-at_install")
class TestRecommendationRules(HomologationTestBase):
    """RF-23, RF-24, RF-25: reglas configurables de recomendación."""

    def setUp(self):
        super().setUp()
        self.env["product.homologation.rule"].search([]).write({"active": False})

    def _alternatives(self, code):
        cheap = self._create_homologation(
            code,
            self.product,
            precision_pct=90.0,
            competitor_id=self.other_competitor,
        )
        expensive = self._create_homologation(
            code,
            self.product_c,
            precision_pct=90.0,
            competitor_id=self.competitor,
        )
        return cheap | expensive

    def _recommend(self, code):
        return self.env["product.homologation"].search(
            [("customer_code", "=", code)]
        )._recommend()

    def test_01_default_rules_are_installed(self):
        precision_rule = self.env.ref(
            "product_homologation.rule_highest_precision"
        )
        price_rule = self.env.ref("product_homologation.rule_lowest_price")

        self.assertEqual(precision_rule.rule_type, "highest_precision")
        self.assertEqual(precision_rule.priority, 10)
        self.assertEqual(price_rule.rule_type, "lowest_price")
        self.assertEqual(price_rule.priority, 20)

    def test_02_highest_precision_rule_recommends_best(self):
        low = self._create_homologation("RULE-PREC", self.product, precision_pct=70.0)
        high = self._create_homologation(
            "RULE-PREC", self.product_b, precision_pct=100.0,
            competitor_id=self.other_competitor,
        )
        self.env["product.homologation.rule"].create({
            "name": "Precisión primero",
            "rule_type": "highest_precision",
            "priority": 10,
        })

        best, reason, ordered = self._recommend("RULE-PREC")

        self.assertEqual(best, high)
        self.assertEqual(reason, "Precisión primero")
        self.assertEqual(ordered[0], high)
        self.assertIn(low, ordered)

    def test_03_lower_priority_rule_breaks_precision_tie(self):
        alternatives = self._alternatives("RULE-TIE")
        self.env["product.homologation.rule"].create({
            "name": "Precisión",
            "rule_type": "highest_precision",
            "priority": 10,
        })
        self.env["product.homologation.rule"].create({
            "name": "Menor precio",
            "rule_type": "lowest_price",
            "priority": 20,
        })
        cheap = alternatives.filtered(lambda h: h.product_id == self.product)

        best, reason, _ordered = self._recommend("RULE-TIE")

        self.assertEqual(cheap.product_price, 100.0)
        self.assertEqual(best, cheap)
        self.assertEqual(reason, "Menor precio")

    def test_04_lowest_cost_rule_uses_standard_price(self):
        # product_b: precio 80 / costo 30; product: precio 100 / costo 40.
        # La regla de costo debe dominar a la de precio de lista (activa por
        # defecto) cuando se configura con mayor prioridad.
        cheap_cost = self._create_homologation(
            "RULE-COST", self.product_b, precision_pct=90.0
        )
        high_cost = self._create_homologation(
            "RULE-COST", self.product, precision_pct=90.0,
            competitor_id=self.other_competitor,
        )
        self.env.ref("product_homologation.rule_highest_precision").active = False
        self.env.ref("product_homologation.rule_lowest_price").active = False
        self.env["product.homologation.rule"].create({
            "name": "Menor costo",
            "rule_type": "lowest_cost",
            "priority": 30,
        })

        best, reason, _ordered = self._recommend("RULE-COST")

        self.assertEqual(cheap_cost.product_standard_price, 30.0)
        self.assertEqual(high_cost.product_standard_price, 40.0)
        self.assertEqual(best, cheap_cost)
        self.assertEqual(reason, "Menor costo")

    def test_05_preferred_competitor_rule_can_dominate(self):
        alternatives = self._alternatives("RULE-COMP")
        self.env["product.homologation"].create({
            "competitor_id": self.competitor.id,
            "customer_code": "RULE-COMP-EXTRA",
            "customer_description": "No participa",
            "product_id": self.product_b.id,
            "state": "validated",
        })
        self.env["product.homologation.rule"].create({
            "name": "Menor precio",
            "rule_type": "lowest_price",
            "priority": 20,
        })
        self.env["product.homologation.rule"].create({
            "name": "Competidor preferido",
            "rule_type": "preferred_competitor",
            "priority": 5,
            "preferred_competitor_id": self.competitor.id,
        })
        preferred = alternatives.filtered(
            lambda h: h.competitor_id == self.competitor
        )

        best, reason, _ordered = self._recommend("RULE-COMP")

        self.assertEqual(best, preferred)
        self.assertEqual(reason, "Competidor preferido")

    def test_06_recommendation_is_only_a_suggestion(self):
        alternatives = self._alternatives("RULE-SUGGEST")
        self.env["product.homologation.rule"].create({
            "name": "Precisión",
            "rule_type": "highest_precision",
            "priority": 10,
        })
        quote = self._create_quote("V2-RULE-SUGGEST")
        line = self._add_line(quote, "RULE-SUGGEST")

        self.assertTrue(line.recommended_homologation_id)
        self.assertFalse(line.homologation_id)

        manual = alternatives.filtered(lambda h: h != line.recommended_homologation_id)
        line.write({"homologation_id": manual.id})

        self.assertEqual(line.homologation_id, manual)

    def test_07_negative_priority_is_rejected(self):
        with self.assertRaises(Exception):
            self.env["product.homologation.rule"].create({
                "name": "Inválida",
                "rule_type": "highest_precision",
                "priority": -5,
            })

    def test_08_inactive_rules_are_ignored(self):
        alternatives = self._alternatives("RULE-INACTIVE")
        cheapest = alternatives.filtered(lambda h: h.product_price == 100.0)
        rule = self.env["product.homologation.rule"].create({
            "name": "Competidor preferido",
            "rule_type": "preferred_competitor",
            "priority": 30,
            "preferred_competitor_id": self.competitor.id,
        })

        best, reason, _ordered = self._recommend("RULE-INACTIVE")
        self.assertNotEqual(best, cheapest)
        self.assertEqual(reason, "Competidor preferido")

        rule.active = False
        best, reason, _ordered = self._recommend("RULE-INACTIVE")

        self.assertEqual(best, cheapest)
        self.assertNotEqual(reason, "Competidor preferido")


@tagged("post_install", "-at_install")
class TestQuoteTotals(HomologationTestBase):
    """RF-26, RF-27, RF-28: totales e indicador global de precisión."""

    def test_01_totals_and_weighted_precision(self):
        exact = self._create_homologation(
            "TOT-EXACT", self.product, precision_pct=100.0
        )
        approximate = self._create_homologation(
            "TOT-APPROX", self.product_b, precision_pct=80.0,
            competitor_id=self.other_competitor,
        )
        quote = self._create_quote("V2-TOT-01")
        self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "TOT-EXACT",
            "customer_description": "Exacta",
            "product_id": self.product.id,
            "homologation_id": exact.id,
            "state": "matched",
            "quantity": 2,
            "price_unit": 100.0,
        })
        self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "TOT-APPROX",
            "customer_description": "Aproximada",
            "product_id": self.product_b.id,
            "homologation_id": approximate.id,
            "state": "matched",
            "quantity": 2,
            "price_unit": 50.0,
        })

        self.assertEqual(quote.total_quantity, 4.0)
        self.assertEqual(quote.total_amount, 300.0)
        self.assertAlmostEqual(quote.global_precision, 93.333333, places=5)

    def test_02_total_quantity_includes_lines_without_product(self):
        quote = self._create_quote("V2-TOT-02")
        self._add_line(quote, "TOT-NOPROD", quantity=5)

        self.assertEqual(quote.total_quantity, 5.0)
        self.assertEqual(quote.total_amount, 0.0)
        self.assertEqual(quote.global_precision, 0.0)

    def test_03_empty_quote_has_zero_totals(self):
        quote = self._create_quote("V2-TOT-03")

        self.assertEqual(quote.total_quantity, 0.0)
        self.assertEqual(quote.total_amount, 0.0)
        self.assertEqual(quote.global_precision, 0.0)
        self.assertEqual(quote.line_count, 0)

    def test_04_totals_update_with_lines(self):
        homologation = self._create_homologation("TOT-UPD", self.product)
        quote = self._create_quote("V2-TOT-04")
        line = self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "TOT-UPD",
            "customer_description": "Actualizable",
            "product_id": self.product.id,
            "homologation_id": homologation.id,
            "state": "matched",
            "quantity": 3,
            "price_unit": 100.0,
        })

        self.assertEqual(quote.total_amount, 300.0)
        line.quantity = 5
        self.assertEqual(quote.total_quantity, 5.0)
        self.assertEqual(quote.total_amount, 500.0)

    def test_05_line_counters(self):
        validated = self._create_homologation("TOT-COUNT-V", self.product)
        provisional = self._create_homologation(
            "TOT-COUNT-P", self.product_b, state="provisional",
            competitor_id=self.other_competitor,
        )
        quote = self._create_quote("V2-TOT-05")
        self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "TOT-COUNT-V",
            "customer_description": "Validada",
            "product_id": self.product.id,
            "homologation_id": validated.id,
            "state": "matched",
        })
        self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "TOT-COUNT-P",
            "customer_description": "Provisional",
            "product_id": self.product_b.id,
            "homologation_id": provisional.id,
            "state": "matched",
        })
        self._add_line(quote, "TOT-COUNT-NONE")

        self.assertEqual(quote.line_count, 3)
        self.assertEqual(quote.matched_count, 1)
        self.assertEqual(quote.provisional_count, 1)


@tagged("post_install", "-at_install")
class TestDuplicateAndVersions(HomologationTestBase):
    """RF-32: duplicación y versionado de precotizaciones."""

    def _quote_with_validated_line(self):
        homologation = self._create_homologation("DUP-001", self.product)
        quote = self._create_quote("V2-DUP-01")
        self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "DUP-001",
            "customer_description": "Línea original",
            "product_id": self.product.id,
            "homologation_id": homologation.id,
            "state": "matched",
            "quantity": 3,
            "price_unit": 100.0,
        })
        return quote, homologation

    def test_01_duplicate_creates_new_version(self):
        quote, homologation = self._quote_with_validated_line()

        action = quote.action_duplicate()
        duplicate = self.env["product.homologation.quote"].browse(action["res_id"])

        self.assertNotEqual(duplicate, quote)
        self.assertEqual(duplicate.state, "draft")
        self.assertEqual(duplicate.version, 2)
        self.assertEqual(duplicate.parent_id, quote)
        self.assertEqual(duplicate.root_id, quote)
        self.assertFalse(duplicate.sale_order_id)
        self.assertTrue(duplicate.name.startswith("PC-"))
        self.assertEqual(len(duplicate.line_ids), 1)
        self.assertEqual(duplicate.line_ids.homologation_id, homologation)
        self.assertEqual(duplicate.line_ids.product_id, self.product)
        self.assertEqual(duplicate.total_amount, 300.0)
        self.assertEqual(action["res_model"], "product.homologation.quote")

    def test_02_duplicate_from_latest_version_keeps_root(self):
        quote, _homologation = self._quote_with_validated_line()
        first = self.env["product.homologation.quote"].browse(
            quote.action_duplicate()["res_id"]
        )
        second = self.env["product.homologation.quote"].browse(
            first.action_duplicate()["res_id"]
        )

        self.assertEqual(second.version, 3)
        self.assertEqual(second.root_id, quote)
        self.assertEqual(second.parent_id, first)
        self.assertEqual(quote.version_count, 3)

    def test_03_view_versions_includes_all_versions(self):
        quote, _homologation = self._quote_with_validated_line()
        duplicate = self.env["product.homologation.quote"].browse(
            quote.action_duplicate()["res_id"]
        )

        action = duplicate.action_view_versions()
        versions = self.env["product.homologation.quote"].search(action["domain"])

        self.assertEqual(set(versions.ids), {quote.id, duplicate.id})
        self.assertEqual(action["res_model"], "product.homologation.quote")

    def test_04_duplicated_quote_can_be_converted_independently(self):
        quote, _homologation = self._quote_with_validated_line()
        duplicate = self.env["product.homologation.quote"].browse(
            quote.action_duplicate()["res_id"]
        )

        duplicate.action_confirm_homologation()
        duplicate.action_convert_to_sale()

        self.assertEqual(duplicate.state, "converted")
        self.assertTrue(duplicate.sale_order_id)
        self.assertEqual(quote.state, "draft")
        self.assertFalse(quote.sale_order_id)

    def test_05_duplicate_of_provisional_quote_does_not_reuse_provisional(self):
        origin = self._create_quote("V2-DUP-PROV")
        line = self._add_line(origin, "DUP-PROV-001", self.product)
        original_homologation = line.homologation_id

        duplicate = self.env["product.homologation.quote"].browse(
            origin.action_duplicate()["res_id"]
        )

        self.assertNotEqual(
            duplicate.line_ids.homologation_id, original_homologation
        )
        self.assertEqual(duplicate.line_ids.match_status, "unmatched")
        with self.assertRaises(UserError):
            duplicate.action_confirm_homologation()

    def test_06_duplicated_quote_writes_chatter_note(self):
        quote, _homologation = self._quote_with_validated_line()
        quote.action_duplicate()

        self.assertTrue(
            quote.message_ids.filtered(
                lambda message: "duplicada" in (message.body or "").lower()
            )
        )


@tagged("post_install", "-at_install")
class TestPriceReview(HomologationTestBase):
    """RF-29, RF-31: revisión del precio al convertir a presupuesto."""

    def _quote_with_price(self, price):
        homologation = self._create_homologation("PRICE-001", self.product)
        quote = self._create_quote("V2-PRICE")
        line = self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "PRICE-001",
            "customer_description": "Producto con precio editado",
            "product_id": self.product.id,
            "homologation_id": homologation.id,
            "state": "matched",
            "quantity": 2,
            "price_unit": price,
        })
        return quote, line

    def test_01_edited_price_is_detected_for_review(self):
        quote, _line = self._quote_with_price(90.0)

        self.assertEqual(quote.price_review_count, 1)
        message = quote._get_price_review_message()
        self.assertIn("Revisión de precios", message)
        self.assertIn("PRICE-001", message)
        self.assertIn("90.00", message)
        self.assertIn("100.00", message)

    def test_02_list_price_has_no_price_review(self):
        quote, _line = self._quote_with_price(100.0)

        self.assertEqual(quote.price_review_count, 0)
        self.assertEqual(quote._get_price_review_message(), "")

    def test_03_conversion_preserves_edited_price(self):
        quote, line = self._quote_with_price(90.0)
        quote.action_confirm_homologation()

        quote.action_convert_to_sale()

        sale_line = quote.sale_order_id.order_line
        self.assertEqual(sale_line.price_unit, 90.0)
        self.assertEqual(sale_line.product_uom_qty, 2)
        self.assertEqual(sale_line.price_subtotal, 180.0)
        self.assertEqual(
            sale_line.homologation_quote_line_id, line
        )

    def test_04_conversion_posts_price_review_message(self):
        quote, _line = self._quote_with_price(90.0)
        quote.action_confirm_homologation()

        quote.action_convert_to_sale()

        self.assertTrue(
            quote.sale_order_id.message_ids.filtered(
                lambda message: "Revisión de precios" in (message.body or "")
            )
        )
        self.assertTrue(
            quote.message_ids.filtered(
                lambda message: "Revisión de precios" in (message.body or "")
            )
        )

    def test_05_conversion_without_price_change_has_no_review_message(self):
        quote, _line = self._quote_with_price(100.0)
        quote.action_confirm_homologation()

        quote.action_convert_to_sale()

        self.assertFalse(
            quote.sale_order_id.message_ids.filtered(
                lambda message: "Revisión de precios" in (message.body or "")
            )
        )


@tagged("post_install", "-at_install")
class TestPermissions(HomologationTestBase):
    """RNF-04: permisos diferenciados de vendedor y especialista."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        seller_group = cls.env.ref(SELLER_GROUP)
        specialist_group = cls.env.ref(SPECIALIST_GROUP)
        cls.seller = cls.env["res.users"].create({
            "name": "Vendedor V2",
            "login": "vendedor_v2_homologation",
            "email": "vendedor_v2@example.com",
            "group_ids": [(6, 0, [seller_group.id])],
        })
        cls.specialist = cls.env["res.users"].create({
            "name": "Especialista V2",
            "login": "especialista_v2_homologation",
            "email": "especialista_v2@example.com",
            "group_ids": [(6, 0, [specialist_group.id])],
        })
        cls.internal = cls.env["res.users"].create({
            "name": "Interno V2",
            "login": "interno_v2_homologation",
            "email": "interno_v2@example.com",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
        })

    def test_01_seller_can_create_but_not_validate(self):
        homologation = self.env["product.homologation"].with_user(self.seller).create({
            "competitor_id": self.competitor.id,
            "customer_code": "PERM-001",
            "customer_description": "Creada por vendedor",
            "product_id": self.product.id,
        })

        self.assertEqual(homologation.state, "draft")
        with self.assertRaises(UserError):
            homologation.with_user(self.seller).action_validate()

    def test_02_specialist_can_validate(self):
        homologation = self._create_homologation(
            "PERM-002", self.product, state="draft"
        )

        homologation.with_user(self.specialist).action_validate()

        self.assertEqual(homologation.state, "validated")
        self.assertEqual(homologation.validator_id, self.specialist)

    def test_03_seller_cannot_write_validated_homologation(self):
        homologation = self._create_homologation("PERM-003", self.product)

        with self.assertRaises(AccessError):
            homologation.with_user(self.seller).write({
                "observation": "Intento de edición",
            })

    def test_04_plain_internal_user_cannot_create_homologation(self):
        with self.assertRaises(AccessError):
            self.env["product.homologation"].with_user(self.internal).create({
                "customer_description": "Sin permisos",
                "product_id": self.product.id,
            })

    def test_05_seller_cannot_unlink_homologation(self):
        homologation = self.env["product.homologation"].with_user(self.seller).create({
            "competitor_id": self.competitor.id,
            "customer_code": "PERM-005",
            "customer_description": "Temporal",
            "product_id": self.product.id,
        })

        with self.assertRaises(AccessError):
            homologation.with_user(self.seller).unlink()

    def test_06_only_specialist_can_manage_rules(self):
        with self.assertRaises(AccessError):
            self.env["product.homologation.rule"].with_user(self.seller).create({
                "name": "Regla de vendedor",
                "rule_type": "highest_precision",
            })
        rule = self.env["product.homologation.rule"].with_user(
            self.specialist
        ).create({
            "name": "Regla de especialista",
            "rule_type": "highest_precision",
        })
        self.assertTrue(rule.exists())

    def test_07_seller_can_manage_quotes(self):
        quote = self.env["product.homologation.quote"].with_user(self.seller).create({
            "partner_id": self.customer.id,
        })
        line = self.env["product.homologation.quote.line"].with_user(
            self.seller
        ).create({
            "quote_id": quote.id,
            "customer_code": "PERM-007",
            "customer_description": "Línea de vendedor",
            "product_id": self.product.id,
        })

        self.assertEqual(line.homologation_id.state, "provisional")
        self.assertEqual(quote.state, "draft")


@tagged("post_install", "-at_install")
class TestModelIntegration(HomologationTestBase):
    """Integración con ventas, chatter y trazabilidad en Odoo 19."""

    def test_01_sale_order_line_keeps_traceability(self):
        homologation = self._create_homologation(
            "INT-001", self.product, observation="Obs homologación",
            homologation_level="near",
        )
        quote = self._create_quote("V2-INT-01")
        self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "INT-001",
            "customer_description": "Descripción original",
            "product_id": self.product.id,
            "homologation_id": homologation.id,
            "state": "matched",
            "quantity": 1,
            "observation": "Obs precotización",
        })
        quote.action_confirm_homologation()

        quote.action_convert_to_sale()

        sale_line = quote.sale_order_id.order_line
        self.assertEqual(sale_line.homologation_id, homologation)
        self.assertEqual(sale_line.homologation_quote_id, quote)
        self.assertEqual(sale_line.homologation_customer_code, "INT-001")
        self.assertEqual(
            sale_line.homologation_customer_description, "Descripción original"
        )
        self.assertEqual(sale_line.homologation_observation, "Obs homologación")
        self.assertEqual(
            sale_line.homologation_quote_observation, "Obs precotización"
        )
        self.assertEqual(sale_line.homologation_level, "near")
        self.assertEqual(sale_line.homologation_precision_pct, 90.0)
        self.assertEqual(homologation.used_in_sale_count, 1)
        with self.assertRaises(UserError):
            homologation.unlink()

    def test_02_quote_chatter_records_activity(self):
        quote = self._create_quote("V2-INT-02")
        quote.action_confirm_homologation()

        self.assertTrue(quote.message_ids)
        self.assertTrue(quote.message_ids[0].body)

    def test_03_quote_form_flow(self):
        homologation = self._create_homologation("INT-003", self.product)
        form = Form(self.env["product.homologation.quote"])
        form.partner_id = self.customer
        with form.line_ids.new() as line:
            line.customer_code = "INT-003"
            line.quantity = 2
        quote = form.save()

        self.assertEqual(len(quote.line_ids), 1)
        self.assertEqual(quote.line_ids.homologation_id, homologation)
        self.assertEqual(quote.total_amount, 200.0)

    def test_04_sale_order_links_quote(self):
        homologation = self._create_homologation("INT-004", self.product)
        quote = self._create_quote("V2-INT-04")
        self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "INT-004",
            "customer_description": "Línea",
            "product_id": self.product.id,
            "homologation_id": homologation.id,
            "state": "matched",
        })
        quote.action_confirm_homologation()
        quote.action_convert_to_sale()

        self.assertEqual(quote.sale_order_id.homologation_quote_id, quote)
        self.assertEqual(quote.sale_order_id.origin, quote.name)
