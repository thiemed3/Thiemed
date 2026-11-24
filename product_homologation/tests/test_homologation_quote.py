from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestHomologationQuote(TransactionCase):
    """Pruebas del flujo de precotización (V1 migrada a Odoo 19 + RF-19/RF-20)."""

    def _create_test_product(self, name, default_code, list_price):
        vals = {
            "name": name,
            "list_price": list_price,
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
            "name": "Cliente CRM",
            "supplier_rank": 1,
        })
        self.customer = self.env["res.partner"].create({
            "name": "Clínica Test",
        })
        self.product = self._create_test_product(
            name="Bisturí Eléctrico",
            default_code="BIS-001",
            list_price=250.0,
        )
        self.product_b = self._create_test_product(
            name="Bisturí Alternativo",
            default_code="BIS-002",
            list_price=300.0,
        )
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

    def _create_validated_alternatives(self, code="ODSH-RULE-001"):
        other_partner = self.env["res.partner"].create({
            "name": "Competidor ODSH Alternativo",
            "supplier_rank": 1,
        })
        first = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": code,
            "customer_description": "ODSH alternative A",
            "product_id": self.product.id,
            "state": "validated",
            "homologation_level": "near",
        })
        second = self.env["product.homologation"].create({
            "competitor_id": other_partner.id,
            "customer_code": code,
            "customer_description": "ODSH alternative B",
            "product_id": self.product_b.id,
            "state": "validated",
            "homologation_level": "exact",
        })
        return first | second

    def _saved_quote_line_for_code(self, code):
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-SAVED-ALTERNATIVES",
        })
        form = Form(quote)
        with form.line_ids.new() as line:
            line.customer_code = code
            line.customer_description = "Line with several alternatives"
        quote = form.save()
        return quote.line_ids[0]

    def test_01_create_quote_gets_sequence_name(self):
        """RF-08: la precotización se crea en borrador con referencia propia."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
        })
        self.assertEqual(quote.state, "draft")
        self.assertTrue(quote.name.startswith("PC-"))
        self.assertEqual(quote.partner_id, self.customer)

    def test_02_add_line_with_onchange_match(self):
        """RF-07/RF-17: un código conocido homologa automáticamente."""
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
        self.assertEqual(line.subtotal, 1250.0)

    def test_03_add_line_without_match(self):
        """RF-07: un código desconocido queda sin match."""
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
        """RF-M06: Homologar todo deja la precotización homologada."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-004",
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
        self.assertEqual(quote.state, "homologated")

    def test_05_convert_to_sale_order(self):
        """RF-M08/RF-30: la conversión crea el presupuesto con trazabilidad."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
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
        self.assertEqual(so.origin, quote.name)
        self.assertEqual(so.homologation_quote_id, quote)

        so_line = so.order_line[0]
        self.assertEqual(so_line.product_id, self.product)
        self.assertEqual(so_line.product_uom_qty, 3)
        self.assertEqual(so_line.price_unit, 240.0)
        self.assertEqual(so_line.homologation_customer_code, "CMP-BIS-001")
        self.assertEqual(so_line.homologation_customer_description, "Electric scalpel")
        self.assertEqual(so_line.homologation_quote_line_id, line)

    def test_06_quote_line_price_from_product(self):
        """RF-24: el precio se toma del producto y puede editarse."""
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

    def test_07_sale_order_line_traceability(self):
        """RF-13/RNF-03: el presupuesto conserva la homologación utilizada."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-007",
        })
        self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "homologation_id": self.homologation.id,
            "quantity": 2,
        })
        quote.action_confirm_homologation()
        quote.action_convert_to_sale()

        so_line = quote.sale_order_id.order_line[0]
        self.assertEqual(so_line.homologation_id, self.homologation)
        self.assertEqual(so_line.homologation_quote_id, quote)
        self.assertEqual(so_line.homologation_precision_pct, 100.0)
        self.assertEqual(self.homologation.used_in_sale_count, 1)
        self.assertTrue(self.homologation.is_used)

    def test_08_form_ui_quote_with_lines(self):
        """RF-M06/RF-M08: flujo completo por UI."""
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
        self.assertEqual(result["res_model"], "sale.order")

    def test_09_cancel_quote(self):
        """RF-08: la precotización puede cancelarse."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-009",
            "state": "homologated",
        })
        quote.action_cancel()
        self.assertEqual(quote.state, "cancelled")

    def test_10_case_insensitive_code_match(self):
        """RF-07: el código se compara sin distinguir mayúsculas."""
        line = self._transient_line_for_code("  cmp-bis-001  ")
        self.assertEqual(line.product_id, self.product)
        self.assertEqual(line.homologation_id, self.homologation)
        self.assertEqual(line.state, "matched")

    def test_11_multiple_validated_codes_do_not_auto_select(self):
        """RF-18: con varias validadas no se elige arbitrariamente."""
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
        """RF-05: un borrador no se usa como match automático."""
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
        """RF-05: una rechazada nunca se usa automáticamente."""
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
        """RF-M06: Homologar todo bloquea líneas incompletas."""
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
        """RF-30: la conversión bloquea líneas pendientes."""
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
        """RF-30: una precotización convertida no genera un segundo presupuesto."""
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
        """RF-03/RF-09: la homologación automática no infiere competidor."""
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
        self.assertEqual(line.homologation_id.state, "provisional")
        self.assertEqual(line.homologation_id.origin_quote_id, quote)
        self.assertFalse(line.homologation_id.competitor_id)

    def test_18_select_validated_alternative(self):
        """RF-18: el usuario puede elegir una alternativa validada."""
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
        """RF-02: una línea solo con descripción no busca por descripción."""
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
        """RF-02: la descripción del cliente es obligatoria."""
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-NO-DESC",
        })

        with self.assertRaises(ValidationError):
            self.env["product.homologation.quote.line"].create({
                "quote_id": quote.id,
                "customer_code": "NO-DESC",
            })

    def test_21_quote_line_price_updates_when_product_changes(self):
        """RF-31: el precio sigue al producto cuando cambia."""
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
        """RF-34/RF-35: las observaciones se conservan al convertir."""
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
        """RF-07: los borradores no cuentan como homologados."""
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
        """RF-07: las validadas cuentan como homologadas."""
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
        """RF-07: las rechazadas no cuentan como homologadas."""
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
        """RF-07: el contador de homologadas solo considera validadas."""
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
        """RF-06: validar la única candidata reconcilia la línea existente."""
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
        self.assertEqual(quote.matched_count, 1)
        quote.action_confirm_homologation()
        self.assertEqual(quote.state, "homologated")

    def test_28_ph022_multiple_validated_do_not_reconcile_automatically(self):
        """RF-18: varias validadas dejan la línea sin resolver."""
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
        """RF-05: una rechazada no se convierte en match."""
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

    def test_30_ph023_transient_multiple_alternatives_cannot_open_button(self):
        """RF-21: una línea sin guardar no puede abrir el popup."""
        alternatives = self._create_validated_alternatives()

        line = self._transient_line_for_code("ODSH-RULE-001")

        self.assertFalse(line.product_id)
        self.assertFalse(line.homologation_id)
        self.assertEqual(line.state, "unmatched")
        self.assertEqual(line.match_status, "alternatives")
        self.assertEqual(line.possible_homologation_count, 2)
        self.assertEqual(set(line.possible_homologation_ids.ids), set(alternatives.ids))
        self.assertFalse(line.can_open_possible_homologations)

    def test_31_ph024_saved_line_keeps_real_alternative_count(self):
        """RF-20: al guardar, las alternativas se mantienen y se cuentan."""
        alternatives = self._create_validated_alternatives()
        self.env["product.homologation.rule"].create({
            "name": "TEST - Priorizar mayor precision",
            "rule_type": "highest_precision",
        })

        line = self._saved_quote_line_for_code("ODSH-RULE-001")

        self.assertFalse(line.product_id)
        self.assertFalse(line.homologation_id)
        self.assertEqual(line.state, "unmatched")
        self.assertEqual(line.match_status, "alternatives")
        self.assertEqual(line.possible_homologation_count, 2)
        self.assertEqual(set(line.possible_homologation_ids.ids), set(alternatives.ids))
        self.assertTrue(line.can_open_possible_homologations)

    def test_32_ph024_action_opens_exactly_validated_alternatives(self):
        """RF-18: la acción solo muestra alternativas válidas del código."""
        alternatives = self._create_validated_alternatives()
        self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "ODSH-RULE-OTHER",
            "customer_description": "Other code",
            "product_id": self.product.id,
            "state": "validated",
        })
        line = self._saved_quote_line_for_code("ODSH-RULE-001")

        action = line.action_open_possible_homologations()

        self.assertEqual(action["res_model"], "product.homologation")
        self.assertEqual(set(action["domain"][0][2]), set(alternatives.ids))

    def test_33_ph024_manual_selection_applies_homologation_and_product(self):
        """RF-18/RF-25: elegir una alternativa aplica producto y precisión."""
        alternatives = self._create_validated_alternatives()
        selected = alternatives.filtered(lambda h: h.product_id == self.product_b)
        line = self._saved_quote_line_for_code("ODSH-RULE-001")

        line.write({"homologation_id": selected.id})

        self.assertEqual(line.homologation_id, selected)
        self.assertEqual(line.product_id, self.product_b)
        self.assertEqual(line.state, "matched")
        self.assertEqual(line.match_status, "validated")

    def test_34_ph024_manual_selection_keeps_alternative_counter(self):
        """RF-20: el contador de alternativas sigue visible tras seleccionar."""
        alternatives = self._create_validated_alternatives()
        selected = alternatives.filtered(lambda h: h.product_id == self.product)
        line = self._saved_quote_line_for_code("ODSH-RULE-001")

        line.write({"homologation_id": selected.id})

        self.assertEqual(line.possible_homologation_count, 2)
        self.assertEqual(
            set(line.possible_homologation_ids.ids), set(alternatives.ids)
        )
        self.assertTrue(line.can_open_possible_homologations)

    def test_35_ph024_single_validated_still_auto_applies(self):
        """RF-17: una única homologación validada se aplica sola."""
        line = self._saved_quote_line_for_code("CMP-BIS-001")

        self.assertEqual(line.homologation_id, self.homologation)
        self.assertEqual(line.product_id, self.product)
        self.assertEqual(line.state, "matched")
        self.assertEqual(line.match_status, "validated")
        self.assertEqual(line.possible_homologation_count, 1)

    def test_36_ph024_draft_and_rejected_are_not_alternatives(self):
        """RF-05: borradores y rechazados no son alternativas."""
        other_partner = self.env["res.partner"].create({
            "name": "Competidor Draft Rejected",
            "supplier_rank": 1,
        })
        draft = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "ODSH-DRAFT-REJECTED",
            "customer_description": "Draft option",
            "product_id": self.product.id,
            "state": "draft",
        })
        rejected = self.env["product.homologation"].create({
            "competitor_id": other_partner.id,
            "customer_code": "ODSH-DRAFT-REJECTED",
            "customer_description": "Rejected option",
            "product_id": self.product_b.id,
            "state": "rejected",
        })

        line = self._saved_quote_line_for_code("ODSH-DRAFT-REJECTED")
        action = line.action_open_possible_homologations()

        self.assertFalse(line.product_id)
        self.assertFalse(line.homologation_id)
        self.assertEqual(line.match_status, "draft")
        self.assertFalse(line.possible_homologation_ids)
        self.assertEqual(line.possible_homologation_count, 0)
        self.assertEqual(set(action["domain"][0][2]), set())
        self.assertNotIn(draft.id, action["domain"][0][2])
        self.assertNotIn(rejected.id, action["domain"][0][2])

    def test_37_ph022_multiple_validation_still_reconciles_alternatives(self):
        """RF-18: validar varias deja las alternativas disponibles."""
        other_partner = self.env["res.partner"].create({
            "name": "PH-022 PH-024 Alternative Competitor",
            "supplier_rank": 1,
        })
        first_homologation = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "PH022-PH024-MULTI-VALIDATE",
            "customer_description": "First PH-022 alternative",
            "product_id": self.product.id,
            "state": "draft",
        })
        second_homologation = self.env["product.homologation"].create({
            "competitor_id": other_partner.id,
            "customer_code": "PH022-PH024-MULTI-VALIDATE",
            "customer_description": "Second PH-022 alternative",
            "product_id": self.product_b.id,
            "state": "draft",
        })
        quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "PRE-PH022-PH024-MULTI",
        })
        line = self.env["product.homologation.quote.line"].create({
            "quote_id": quote.id,
            "customer_code": "PH022-PH024-MULTI-VALIDATE",
            "customer_description": "Ambiguous PH-022 quote line",
            "state": "unmatched",
        })

        (first_homologation | second_homologation).action_validate()
        action = line.action_open_possible_homologations()

        self.assertFalse(line.homologation_id)
        self.assertFalse(line.product_id)
        self.assertEqual(line.state, "unmatched")
        self.assertEqual(line.match_status, "alternatives")
        self.assertEqual(line.possible_homologation_count, 2)
        self.assertEqual(
            set(line.possible_homologation_ids.ids),
            {first_homologation.id, second_homologation.id},
        )
        self.assertEqual(
            set(action["domain"][0][2]),
            {first_homologation.id, second_homologation.id},
        )
        self.assertEqual(quote.matched_count, 0)

    def test_38_ph025_alternatives_action_only_contains_compatible_records(self):
        """RF-18: la acción de alternativas queda acotada y explícita."""
        alternatives = self._create_validated_alternatives("LOCAL-PH025-001")
        incompatible = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "LOCAL-PH025-OTHER",
            "customer_description": "Other validated homologation",
            "product_id": self.product.id,
            "state": "validated",
        })
        line = self._saved_quote_line_for_code("LOCAL-PH025-001")

        action = line.action_open_possible_homologations()

        self.assertEqual(set(action["domain"][0][2]), set(alternatives.ids))
        self.assertNotIn(incompatible.id, action["domain"][0][2])
        self.assertEqual(action["context"]["homologation_quote_line_id"], line.id)
        self.assertFalse(action["context"]["create"])
        self.assertFalse(action["context"]["edit"])
        self.assertFalse(action["context"]["delete"])
        self.assertEqual(action["views"], [
            (
                self.env.ref(
                    "product_homologation.view_product_homologation_possible_tree"
                ).id,
                "list",
            ),
            (
                self.env.ref(
                    "product_homologation.view_product_homologation_possible_form"
                ).id,
                "form",
            ),
        ])

    def test_39_ph025_apply_alternative_a_updates_line_and_quote(self):
        """RF-18: seleccionar la alternativa A actualiza línea y contadores."""
        alternatives = self._create_validated_alternatives("LOCAL-PH025-APPLY-A")
        selected = alternatives.filtered(lambda h: h.precision_pct == 90.0)
        line = self._saved_quote_line_for_code("LOCAL-PH025-APPLY-A")
        self.assertEqual(line.possible_homologation_count, 2)

        result = selected.with_context(
            line.action_open_possible_homologations()["context"]
        ).action_apply_to_quote_line()

        self.assertEqual(result["res_model"], "product.homologation.quote")
        self.assertEqual(result["res_id"], line.quote_id.id)
        self.assertEqual(line.homologation_id, selected)
        self.assertEqual(line.product_id, self.product)
        self.assertEqual(line.state, "matched")
        self.assertEqual(line.match_status, "validated")
        self.assertEqual(line.homologation_level, "near")
        self.assertEqual(line.homologation_precision_pct, 90.0)
        self.assertEqual(line.quote_id.matched_count, 1)

    def test_40_ph025_apply_alternative_b_updates_line_and_quote(self):
        """RF-18: seleccionar la alternativa B aplica su producto y precisión."""
        alternatives = self._create_validated_alternatives("LOCAL-PH025-APPLY-B")
        selected = alternatives.filtered(lambda h: h.precision_pct == 100.0)
        line = self._saved_quote_line_for_code("LOCAL-PH025-APPLY-B")

        selected.with_context(
            line.action_open_possible_homologations()["context"]
        ).action_apply_to_quote_line()

        self.assertEqual(line.homologation_id, selected)
        self.assertEqual(line.product_id, self.product_b)
        self.assertEqual(line.state, "matched")
        self.assertEqual(line.match_status, "validated")
        self.assertEqual(line.homologation_level, "exact")
        self.assertEqual(line.homologation_precision_pct, 100.0)
        self.assertEqual(line.quote_id.matched_count, 1)

    def test_41_ph025_incompatible_homologation_cannot_be_applied(self):
        """RF-18: no se aplican homologaciones de otro código."""
        self._create_validated_alternatives("LOCAL-PH025-INCOMPATIBLE")
        incompatible = self.env["product.homologation"].create({
            "competitor_id": self.partner.id,
            "customer_code": "LOCAL-PH025-WRONG-CODE",
            "customer_description": "Wrong code homologation",
            "product_id": self.product_b.id,
            "state": "validated",
        })
        line = self._saved_quote_line_for_code("LOCAL-PH025-INCOMPATIBLE")

        with self.assertRaises(UserError):
            line.write({"homologation_id": incompatible.id})
        with self.assertRaises(UserError):
            incompatible.with_context(
                homologation_quote_line_id=line.id
            ).action_apply_to_quote_line()

        self.assertFalse(line.homologation_id)
        self.assertFalse(line.product_id)
        self.assertEqual(line.match_status, "alternatives")
        self.assertEqual(line.possible_homologation_count, 2)
        self.assertEqual(line.quote_id.matched_count, 0)

    def test_42_ph025_single_validated_still_auto_applies(self):
        """RF-17: con una sola validada el match sigue siendo automático."""
        line = self._saved_quote_line_for_code("CMP-BIS-001")

        self.assertEqual(line.homologation_id, self.homologation)
        self.assertEqual(line.product_id, self.product)
        self.assertEqual(line.state, "matched")
        self.assertEqual(line.match_status, "validated")
        self.assertEqual(line.possible_homologation_count, 1)
        self.assertEqual(line.quote_id.matched_count, 1)
