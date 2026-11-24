import base64
import io

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class HomologationImportTestBase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.competitor = cls.env["res.partner"].create({
            "name": "Marca Importación",
            "supplier_rank": 1,
        })
        cls.customer = cls.env["res.partner"].create({"name": "Cliente Importación"})
        cls.product = cls._create_product("Producto Import A", "IMP-A", 100.0)
        cls.product_b = cls._create_product("Producto Import B", "IMP-B", 50.0)

    @classmethod
    def _create_product(cls, name, code, list_price):
        values = {"name": name, "list_price": list_price}
        if "base_unit_count" in cls.env["product.template"]._fields:
            values["base_unit_count"] = 1
        template = cls.env["product.template"].create(values)
        product = template.product_variant_id
        product.default_code = code
        return product

    def _payload(self, content):
        if isinstance(content, str):
            content = content.encode("utf-8")
        return base64.b64encode(content).decode()

    def _run_homologation_import(self, content, filename="homologaciones.csv", **extra):
        values = {
            "file": self._payload(content),
            "filename": filename,
        }
        values.update(extra)
        wizard = self.env["product.homologation.import.wizard"].create(values)
        wizard.action_import()
        return wizard

    def _run_quote_import(self, quote, content, filename="precotizacion.csv", **extra):
        values = {
            "quote_id": quote.id,
            "file": self._payload(content),
            "filename": filename,
        }
        values.update(extra)
        wizard = self.env["product.homologation.quote.import.wizard"].create(values)
        wizard.action_import()
        return wizard

    @staticmethod
    def _xlsx(rows):
        import openpyxl

        workbook = openpyxl.Workbook()
        sheet = workbook.active
        for row in rows:
            sheet.append(row)
        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()


@tagged("post_install", "-at_install")
class TestHomologationExcelImport(HomologationImportTestBase):
    """RF-14, RNF-06: importación masiva de homologaciones."""

    def test_01_csv_import_creates_homologations(self):
        content = (
            "Código cliente;Descripción;Marca;Código interno;Nivel;Precisión\n"
            "IMP-CSV-001;Bisturí de prueba;Marca Importación;IMP-A;cercana;90\n"
            "IMP-CSV-002;Tijera de prueba;Marca Importación;IMP-B;exacta;100\n"
        )

        wizard = self._run_homologation_import(content)

        self.assertEqual(wizard.created_count, 2)
        self.assertEqual(wizard.error_count, 0)
        self.assertIn("Creados: 2", wizard.result)

        first = self.env["product.homologation"].search([
            ("customer_code", "=", "IMP-CSV-001"),
        ])
        self.assertEqual(len(first), 1)
        self.assertEqual(first.product_id, self.product)
        self.assertEqual(first.competitor_id, self.competitor)
        self.assertEqual(first.homologation_level, "near")
        self.assertEqual(first.precision_pct, 90.0)
        self.assertEqual(first.state, "draft")

    def test_02_csv_import_reports_invalid_rows(self):
        content = (
            "Código cliente;Descripción;Marca;Código interno;Nivel;Precisión\n"
            "IMP-ERR-001;Válida;Marca Importación;IMP-A;exacta;100\n"
            "IMP-ERR-002;;Marca Importación;IMP-A;exacta;100\n"
            "IMP-ERR-003;Producto inexistente;Marca Importación;NO-EXISTE;exacta;100\n"
            "IMP-ERR-004;Precisión inválida;Marca Importación;IMP-A;exacta;150\n"
            "IMP-ERR-005;Marca inexistente;Marca Fantasma;IMP-A;exacta;100\n"
        )

        wizard = self._run_homologation_import(content)

        self.assertEqual(wizard.created_count, 1)
        self.assertEqual(wizard.error_count, 4)
        self.assertIn("Fila 3", wizard.error_log)
        self.assertIn("Fila 4", wizard.error_log)
        self.assertIn("Fila 5", wizard.error_log)
        self.assertIn("Fila 6", wizard.error_log)
        self.assertFalse(
            self.env["product.homologation"].search([
                ("customer_code", "in", [
                    "IMP-ERR-002", "IMP-ERR-003", "IMP-ERR-004", "IMP-ERR-005",
                ]),
            ])
        )

    def test_03_csv_import_detects_duplicate_rows_in_file(self):
        content = (
            "Código cliente;Descripción;Marca;Código interno\n"
            "IMP-DUP-001;Primera;Marca Importación;IMP-A\n"
            "imp-dup-001;Segunda;Marca Importación;IMP-B\n"
        )

        wizard = self._run_homologation_import(content)

        self.assertEqual(wizard.created_count, 1)
        self.assertEqual(wizard.error_count, 1)
        self.assertIn("duplicado", wizard.error_log)

    def test_04_csv_import_skips_existing_by_default(self):
        existing = self.env["product.homologation"].create({
            "competitor_id": self.competitor.id,
            "customer_code": "IMP-EXIST-001",
            "customer_description": "Original",
            "product_id": self.product.id,
            "state": "validated",
        })
        content = (
            "Código cliente;Descripción;Marca;Código interno\n"
            "IMP-EXIST-001;Actualizada;Marca Importación;IMP-B\n"
            "IMP-EXIST-002;Nueva;Marca Importación;IMP-A\n"
        )

        wizard = self._run_homologation_import(content)

        self.assertEqual(wizard.created_count, 1)
        self.assertEqual(wizard.skipped_count, 1)
        self.assertEqual(existing.customer_description, "Original")
        self.assertEqual(existing.product_id, self.product)

    def test_05_csv_import_updates_existing_when_requested(self):
        existing = self.env["product.homologation"].create({
            "competitor_id": self.competitor.id,
            "customer_code": "IMP-UPD-001",
            "customer_description": "Original",
            "product_id": self.product.id,
            "state": "validated",
        })
        content = (
            "Código cliente;Descripción;Marca;Código interno\n"
            "IMP-UPD-001;Actualizada;Marca Importación;IMP-B\n"
        )

        wizard = self._run_homologation_import(content, update_existing=True)

        self.assertEqual(wizard.updated_count, 1)
        self.assertEqual(wizard.created_count, 0)
        self.assertEqual(existing.customer_description, "Actualizada")
        self.assertEqual(existing.product_id, self.product_b)

    def test_06_csv_import_can_create_missing_competitors(self):
        content = (
            "Código cliente;Descripción;Marca;Código interno\n"
            "IMP-BRAND-001;Producto;Marca Nueva Importación;IMP-A\n"
        )

        wizard = self._run_homologation_import(content, create_competitors=True)

        self.assertEqual(wizard.created_count, 1)
        partner = self.env["res.partner"].search([
            ("name", "=", "Marca Nueva Importación"),
        ])
        self.assertEqual(len(partner), 1)
        self.assertTrue(partner.supplier_rank > 0)
        homologation = self.env["product.homologation"].search([
            ("customer_code", "=", "IMP-BRAND-001"),
        ])
        self.assertEqual(homologation.competitor_id, partner)

    def test_07_xlsx_import_creates_homologations(self):
        content = self._xlsx([
            ["Código cliente", "Descripción", "Marca", "Código interno", "Nivel"],
            ["IMP-XLSX-001", "Bisturí xlsx", "Marca Importación", "IMP-A", "exacta"],
            ["IMP-XLSX-002", "Tijera xlsx", "Marca Importación", "IMP-B", "mejor"],
        ])

        wizard = self._run_homologation_import(
            content, filename="homologaciones.xlsx"
        )

        self.assertEqual(wizard.created_count, 2)
        self.assertEqual(wizard.error_count, 0)
        homologation = self.env["product.homologation"].search([
            ("customer_code", "=", "IMP-XLSX-002"),
        ])
        self.assertEqual(homologation.homologation_level, "best")
        self.assertEqual(homologation.precision_pct, 70.0)

    def test_08_empty_file_is_rejected(self):
        wizard = self.env["product.homologation.import.wizard"].create({
            "file": self._payload("Código cliente;Descripción\n"),
            "filename": "vacio.csv",
        })

        with self.assertRaises(UserError):
            wizard.action_import()


@tagged("post_install", "-at_install")
class TestQuoteExcelImport(HomologationImportTestBase):
    """RF-15, RF-16: importación de líneas de precotización con matching."""

    def setUp(self):
        super().setUp()
        self.homologation = self.env["product.homologation"].create({
            "competitor_id": self.competitor.id,
            "customer_code": "QIMP-001",
            "customer_description": "Producto homologado",
            "product_id": self.product.id,
            "state": "validated",
        })
        self.quote = self.env["product.homologation.quote"].create({
            "partner_id": self.customer.id,
            "name": "V2-QIMP-01",
        })

    def test_01_csv_import_creates_lines_and_applies_matching(self):
        content = (
            "Código cliente;Descripción;Marca;Cantidad;Precio\n"
            "QIMP-001;Producto homologado;Marca Importación;2;90\n"
            "QIMP-999;Producto sin homologar;;3;20\n"
        )

        wizard = self._run_quote_import(self.quote, content)

        self.assertEqual(wizard.created_count, 2)
        self.assertEqual(wizard.error_count, 0)
        self.assertEqual(self.quote.line_count, 2)

        matched = self.quote.line_ids.filtered(
            lambda line: line.customer_code == "QIMP-001"
        )
        self.assertEqual(matched.product_id, self.product)
        self.assertEqual(matched.homologation_id, self.homologation)
        self.assertEqual(matched.state, "matched")
        self.assertEqual(matched.match_status, "validated")
        self.assertEqual(matched.quantity, 2.0)
        self.assertEqual(matched.price_unit, 90.0)
        self.assertEqual(matched.subtotal, 180.0)

        unmatched = self.quote.line_ids.filtered(
            lambda line: line.customer_code == "QIMP-999"
        )
        self.assertFalse(unmatched.product_id)
        self.assertFalse(unmatched.homologation_id)
        self.assertEqual(unmatched.match_status, "unmatched")

        self.assertEqual(self.quote.total_quantity, 5.0)
        self.assertEqual(self.quote.total_amount, 240.0)

    def test_02_csv_import_reports_invalid_rows(self):
        content = (
            "Código cliente;Descripción;Marca;Cantidad;Precio\n"
            "QIMP-001;Válida;Marca Importación;1;10\n"
            ";Sin código;;1;10\n"
            "QIMP-003;;Marca Importación;1;10\n"
            "QIMP-004;Cantidad inválida;Marca Importación;0;10\n"
            "QIMP-005;Marca inválida;Marca Fantasma;1;10\n"
            "QIMP-006;Precio inválido;Marca Importación;1;-5\n"
        )

        wizard = self._run_quote_import(self.quote, content)

        self.assertEqual(wizard.created_count, 1)
        self.assertEqual(wizard.error_count, 5)
        self.assertIn("Fila 3", wizard.error_log)
        self.assertIn("Fila 4", wizard.error_log)
        self.assertIn("Fila 5", wizard.error_log)
        self.assertIn("Fila 6", wizard.error_log)
        self.assertIn("Fila 7", wizard.error_log)
        self.assertEqual(self.quote.line_count, 1)
        self.assertEqual(self.quote.line_ids.customer_code, "QIMP-001")

    def test_03_import_appends_after_existing_lines(self):
        self.env["product.homologation.quote.line"].create({
            "quote_id": self.quote.id,
            "customer_code": "QIMP-EXIST",
            "customer_description": "Línea previa",
            "sequence": 50,
        })
        content = (
            "Código cliente;Descripción;Cantidad\n"
            "QIMP-001;Importada;1\n"
        )

        self._run_quote_import(self.quote, content)

        imported = self.quote.line_ids.filtered(
            lambda line: line.customer_code == "QIMP-001"
        )
        self.assertGreater(imported.sequence, 50)

    def test_04_xlsx_import_creates_lines(self):
        content = self._xlsx([
            ["Código cliente", "Descripción", "Marca", "Cantidad", "Precio"],
            ["QIMP-001", "Producto xlsx", "Marca Importación", 4, 25],
        ])

        wizard = self._run_quote_import(
            self.quote, content, filename="precotizacion.xlsx"
        )

        self.assertEqual(wizard.created_count, 1)
        line = self.quote.line_ids
        self.assertEqual(line.quantity, 4.0)
        self.assertEqual(line.price_unit, 25.0)
        self.assertEqual(line.homologation_id, self.homologation)
        self.assertEqual(self.quote.total_amount, 100.0)

    def test_05_import_without_matching_requires_product_manually(self):
        content = (
            "Código cliente;Descripción;Cantidad\n"
            "QIMP-001;Sin matching;1\n"
        )

        self._run_quote_import(self.quote, content, match_homologations=False)

        line = self.quote.line_ids
        self.assertEqual(line.homologation_id, self.homologation)
        self.assertEqual(line.state, "matched")

    def test_06_empty_file_is_rejected(self):
        wizard = self.env["product.homologation.quote.import.wizard"].create({
            "quote_id": self.quote.id,
            "file": self._payload("Código cliente;Descripción\n"),
            "filename": "vacio.csv",
        })

        with self.assertRaises(UserError):
            wizard.action_import()

    def test_07_quote_button_opens_import_wizard(self):
        action = self.quote.action_import_lines()

        self.assertEqual(
            action["res_model"], "product.homologation.quote.import.wizard"
        )
        self.assertEqual(action["context"]["default_quote_id"], self.quote.id)
