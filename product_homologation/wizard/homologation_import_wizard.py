import base64
import logging
from difflib import SequenceMatcher

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import openpyxl
except ImportError:
    _logger.warning("openpyxl no está disponible.")
    openpyxl = None

FUZZY_THRESHOLD = 0.6


class ProductHomologationImportWizard(models.TransientModel):
    _name = "product.homologation.import.wizard"
    _description = "Importar homologaciones desde Excel"

    file = fields.Binary(string="Archivo Excel", required=True)
    filename = fields.Char(string="Nombre del archivo")
    competitor_id = fields.Many2one(
        "res.partner",
        string="Competidor/Marca",
        required=True,
        domain=[("competitor", "=", True)],
    )
    state = fields.Selection(
        [("import", "Importar"), ("result", "Resultado")],
        default="import",
        required=True,
    )
    imported_count = fields.Integer(readonly=True)
    matched_count = fields.Integer(readonly=True)
    fuzzy_count = fields.Integer(string="Match aproximado", readonly=True)
    unmatched_count = fields.Integer(readonly=True)
    error_count = fields.Integer(readonly=True)
    result_summary = fields.Text(readonly=True)

    def action_import(self):
        self.ensure_one()
        if not openpyxl:
            raise UserError("openpyxl no está instalado. Ejecute: pip install openpyxl")

        file_data = base64.b64decode(self.file)
        wb = openpyxl.load_workbook(file_data, read_only=True)
        ws = wb.active

        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            raise UserError("El archivo Excel está vacío.")

        header = [str(c or "").strip().lower() for c in rows[0]]
        data_rows = rows[1:]

        col_code = self._find_column(header, ["código", "codigo", "code", "sku", "cod"])
        col_desc = self._find_column(
            header, ["descripción", "descripcion", "description", "nombre", "name", "producto"]
        )
        col_int = self._find_column(
            header,
            ["código interno", "codigo interno", "internal code", "internal_code", "default_code", "ref"],
        )

        if col_code is None:
            raise UserError(
                "No se encontró columna de código. "
                "El Excel debe tener una columna 'Código' o 'SKU'."
            )

        Product = self.env["product.product"]
        Homologation = self.env["product.homologation"]
        Rule = self.env["product.homologation.rule"]

        active_rules = Rule.search([("active", "=", True)], order="priority")

        imported = 0
        matched = 0
        fuzzy = 0
        unmatched = 0
        errors = 0
        detail_lines = []

        product_cache = {}

        for i, row in enumerate(data_rows, start=2):
            if not row or not any(row):
                continue
            try:
                if col_code >= len(row):
                    continue
                customer_code = str(row[col_code] or "").strip()
                if not customer_code:
                    continue

                customer_desc = ""
                if col_desc is not None and row[col_desc]:
                    customer_desc = str(row[col_desc]).strip()

                internal_code = ""
                if col_int is not None and row[col_int]:
                    internal_code = str(row[col_int]).strip()

                result = self._find_product(
                    Product, active_rules, product_cache,
                    internal_code, customer_code, customer_desc,
                )

                vals = {
                    "competitor_id": self.competitor_id.id,
                    "customer_code": customer_code,
                    "customer_description": customer_desc,
                }

                if result:
                    product_id, precision = result
                    vals["product_id"] = product_id.id
                    vals["precision_pct"] = precision
                    if precision >= 100.0:
                        vals["state"] = "validated"
                        matched += 1
                    else:
                        vals["state"] = "draft"
                        fuzzy += 1
                else:
                    vals["state"] = "draft"
                    unmatched += 1

                Homologation.create(vals)
                imported += 1

            except Exception as e:
                errors += 1
                detail_lines.append(f"Fila {i}: {e}")
                _logger.warning("Error fila %s: %s", i, e)

        wb.close()

        detail = (
            f"Total procesadas: {imported}\n"
            f"Match exacto (100%): {matched}\n"
            f"Match aproximado: {fuzzy}\n"
            f"Sin match: {unmatched}\n"
            f"Errores: {errors}\n"
        )
        if detail_lines:
            detail += "\nErrores:\n" + "\n".join(detail_lines[:20])
            if len(detail_lines) > 20:
                detail += f"\n... y {len(detail_lines) - 20} más."

        self.write({
            "state": "result",
            "imported_count": imported,
            "matched_count": matched,
            "fuzzy_count": fuzzy,
            "unmatched_count": unmatched,
            "error_count": errors,
            "result_summary": detail,
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": "product.homologation.import.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def action_close(self):
        return {"type": "ir.actions.act_window_close"}

    def _find_column(self, header, candidates):
        for i, col_name in enumerate(header):
            for c in candidates:
                if c in col_name:
                    return i
        return None

    def _find_product(self, Product, rules, cache, internal_code, customer_code, customer_desc):
        if internal_code:
            product = Product.search([("default_code", "=", internal_code)], limit=1)
            if product:
                return product, 100.0

        product = Product.search([("default_code", "=", customer_code)], limit=1)
        if product:
            return product, 100.0

        product = Product.search([("default_code", "=", customer_code.replace(" ", ""))], limit=1)
        if product:
            return product, 90.0

        if customer_desc:
            product = Product.search([("name", "ilike", customer_desc)], limit=1)
            if product:
                return product, 80.0

        if customer_code:
            like_code = Product.search([("default_code", "ilike", f"%{customer_code}%")], limit=5)
            if like_code:
                return like_code[0], 70.0

        if customer_desc:
            match = self._fuzzy_search(Product, customer_desc)
            if match:
                return match["product"], match["score"]

        preferred_rule = rules.filtered(lambda r: r.rule_type == "preferred_competitor")
        if preferred_rule and customer_desc:
            match = self._fuzzy_search(Product, customer_desc)
            if match:
                return match["product"], match["score"]

        return None

    def _fuzzy_search(self, Product, query):
        if not query:
            return None
        q = query.lower().strip()
        best = None
        all_products = Product.search([], limit=500)
        for p in all_products:
            score = SequenceMatcher(None, q, p.name.lower()).ratio()
            if score > FUZZY_THRESHOLD and (best is None or score > best["score"]):
                best = {"product": p, "score": round(score * 100, 1)}
        return best
