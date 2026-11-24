"""Carga masiva de homologaciones y de líneas de precotización (RF-14, RF-15, RF-16).

Se aceptan archivos ``.xlsx``, ``.xls`` y ``.csv`` (separador ``;``, ``,``,
tab o ``|``). El archivo se valida fila por fila antes de crear datos: las
filas inválidas no se incorporan y quedan reportadas en el asistente
(RNF-06).
"""
import base64
import csv
import io
import logging
import unicodedata

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

LEVEL_ALIASES = {
    "exact": "exact",
    "exacta": "exact",
    "coincidencia exacta": "exact",
    "near": "near",
    "cercana": "near",
    "coincidencia cercana": "near",
    "approximate": "approximate",
    "aproximada": "approximate",
    "coincidencia aproximada": "approximate",
    "best": "best",
    "mejor": "best",
    "mejor opcion": "best",
}

CODE_KEYS = ("codigo_cliente", "codigo", "customer_code", "sku_cliente", "referencia")
DESCRIPTION_KEYS = (
    "descripcion", "descripcion_cliente", "customer_description", "producto",
    "glosa",
)
BRAND_KEYS = ("marca", "competidor", "competitor", "brand", "marca_competidor")
PRODUCT_KEYS = (
    "codigo_interno", "sku_interno", "product_code", "default_code",
    "codigo_thiemed", "codigo_producto",
)
LEVEL_KEYS = ("nivel", "nivel_homologacion", "homologation_level", "nivel_de_homologacion")
PRECISION_KEYS = ("precision", "precision_pct", "porcentaje_precision", "precio_precision")
OBSERVATION_KEYS = ("observacion", "observation", "obs", "comentario")
QUANTITY_KEYS = ("cantidad", "quantity", "qty", "unidades")
PRICE_KEYS = ("precio", "precio_unitario", "price_unit", "price", "valor")


def normalize_header(value):
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("%", " pct ")
    cleaned = []
    for char in text:
        cleaned.append(char if char.isalnum() else "_")
    text = "".join(cleaned)
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def normalize_text(value):
    if value is None:
        return ""
    text = str(value).strip()
    text = unicodedata.normalize("NFKD", text)
    return "".join(char for char in text if not unicodedata.combining(char)).lower()


def pick(row, keys):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def to_text(value):
    if value in (None, False):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def to_float(value, default=0.0):
    if value in (None, ""):
        return default
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def read_tabular_file(content, filename):
    """Devuelve (headers, rows) de un archivo xlsx, xls o csv."""
    name = (filename or "").lower()
    if name.endswith(".xlsx"):
        import openpyxl

        workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        sheet = workbook.active
        values = list(sheet.iter_rows(values_only=True))
        if not values:
            return [], []
        headers = [normalize_header(value) for value in values[0]]
        rows = []
        for raw in values[1:]:
            if all(value in (None, "") for value in raw):
                continue
            rows.append({headers[index]: raw[index] for index in range(len(headers))})
        return headers, rows
    if name.endswith(".xls"):
        import xlrd

        book = xlrd.open_workbook(file_contents=content)
        sheet = book.sheet_by_index(0)
        headers = [normalize_header(sheet.cell_value(0, column)) for column in range(sheet.ncols)]
        rows = []
        for row_index in range(1, sheet.nrows):
            row = {
                headers[column]: sheet.cell_value(row_index, column)
                for column in range(sheet.ncols)
            }
            if all(value in (None, "") for value in row.values()):
                continue
            rows.append(row)
        return headers, rows
    text = content.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = [normalize_header(header) for header in (reader.fieldnames or [])]
    rows = []
    for raw in reader:
        rows.append({
            normalize_header(key): value
            for key, value in raw.items()
            if key is not None
        })
    return headers, rows


class HomologationImportMixin(models.AbstractModel):
    _name = "product.homologation.import.mixin"
    _description = "Utilidades de carga masiva"

    file = fields.Binary(string="Archivo", required=True)
    filename = fields.Char(string="Nombre del archivo")
    result = fields.Text(string="Resultado", readonly=True)
    error_log = fields.Text(string="Errores detectados", readonly=True)
    created_count = fields.Integer(string="Creados", readonly=True)
    updated_count = fields.Integer(string="Actualizados", readonly=True)
    skipped_count = fields.Integer(string="Omitidos", readonly=True)
    error_count = fields.Integer(string="Errores", readonly=True)

    def _read_upload(self):
        self.ensure_one()
        if not self.file:
            raise UserError(_("Debe adjuntar un archivo."))
        content = base64.b64decode(self.file)
        headers, rows = read_tabular_file(content, self.filename)
        if not headers or not rows:
            raise UserError(_(
                "El archivo no contiene datos o no se pudo leer. "
                "Verifique el formato (.xlsx, .xls o .csv)."
            ))
        return headers, rows

    def _reset_counters(self):
        self.write({
            "created_count": 0,
            "updated_count": 0,
            "skipped_count": 0,
            "error_count": 0,
        })

    def _finish_import(self, created, updated, skipped, errors):
        summary = _(
            "Filas procesadas: %(rows)s. Creados: %(created)s. "
            "Actualizados: %(updated)s. Omitidos: %(skipped)s. Errores: %(errors)s."
        ) % {
            "rows": created + updated + skipped + len(errors),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": len(errors),
        }
        self.write({
            "created_count": created,
            "updated_count": updated,
            "skipped_count": skipped,
            "error_count": len(errors),
            "result": summary,
            "error_log": "\n".join(errors) if errors else False,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Resultado de la importación"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": {"import_done": True},
        }


class ProductHomologationImportWizard(models.TransientModel):
    _name = "product.homologation.import.wizard"
    _inherit = ["product.homologation.import.mixin"]
    _description = "Importar homologaciones desde Excel"

    update_existing = fields.Boolean(
        string="Actualizar homologaciones existentes",
        default=False,
        help="Si está marcado, las filas que ya existen para el mismo "
             "competidor y código actualizan producto y descripción. "
             "Si no, se omiten y quedan contabilizadas.",
    )
    create_competitors = fields.Boolean(
        string="Crear marcas/competidores inexistentes",
        default=False,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
        required=True,
    )

    def _resolve_level(self, value):
        if not value:
            return "exact"
        return LEVEL_ALIASES.get(normalize_text(value), "exact")

    def _resolve_product(self, code, cache):
        code = to_text(code)
        if code in cache:
            return cache[code]
        product = self.env["product.product"].search(
            [("default_code", "=ilike", code)], limit=1
        )
        cache[code] = product
        return product

    def _resolve_competitor(self, name):
        name = to_text(name)
        if not name:
            return self.env["res.partner"]
        partner = self.env["res.partner"].search([("name", "=ilike", name)], limit=1)
        if not partner and self.create_competitors:
            partner = self.env["res.partner"].create({
                "name": name,
                "supplier_rank": 1,
            })
        return partner

    def action_import(self):
        self.ensure_one()
        self._reset_counters()
        _headers, rows = self._read_upload()
        product_cache = {}
        seen = set()
        created = updated = skipped = 0
        errors = []
        for index, row in enumerate(rows, start=2):
            description = to_text(pick(row, DESCRIPTION_KEYS))
            code = to_text(pick(row, CODE_KEYS))
            product_code = to_text(pick(row, PRODUCT_KEYS))
            if not description:
                errors.append(_("Fila %(row)s: falta la descripción del cliente.")
                              % {"row": index})
                continue
            if not product_code:
                errors.append(_("Fila %(row)s: falta el código interno del producto.")
                              % {"row": index})
                continue
            product = self._resolve_product(product_code, product_cache)
            if not product:
                errors.append(_(
                    "Fila %(row)s: no existe un producto interno con código %(code)s."
                ) % {"row": index, "code": product_code})
                continue
            brand_name = to_text(pick(row, BRAND_KEYS))
            competitor = self._resolve_competitor(brand_name)
            if brand_name and not competitor:
                errors.append(_(
                    "Fila %(row)s: no existe la marca/competidor %(brand)s."
                ) % {"row": index, "brand": brand_name})
                continue
            key = ((competitor.id or 0), code.casefold())
            if key in seen:
                errors.append(_(
                    "Fila %(row)s: el código %(code)s está duplicado en el archivo."
                ) % {"row": index, "code": code})
                continue
            seen.add(key)
            level = self._resolve_level(pick(row, LEVEL_KEYS))
            precision_raw = pick(row, PRECISION_KEYS)
            precision = to_float(precision_raw, default=None)
            if precision is not None and not 0.0 <= precision <= 100.0:
                errors.append(_(
                    "Fila %(row)s: la precisión debe estar entre 0 y 100."
                ) % {"row": index})
                continue
            values = {
                "competitor_id": competitor.id or False,
                "customer_code": code or False,
                "customer_description": description,
                "product_id": product.id,
                "homologation_level": level,
                "observation": to_text(pick(row, OBSERVATION_KEYS)) or False,
            }
            if precision is not None:
                values["precision_pct"] = precision
            domain = [
                ("company_id", "=", self.company_id.id),
                ("competitor_id", "=", competitor.id or False),
                ("customer_code", "=ilike", code),
            ] if code else [
                ("company_id", "=", self.company_id.id),
                ("competitor_id", "=", competitor.id or False),
                ("customer_code", "=", False),
                ("customer_description", "=", description),
            ]
            existing = self.env["product.homologation"].search(domain, limit=1)
            if existing:
                if not self.update_existing:
                    skipped += 1
                    continue
                existing.write(values)
                updated += 1
                continue
            values["company_id"] = self.company_id.id
            self.env["product.homologation"].create(values)
            created += 1
        return self._finish_import(created, updated, skipped, errors)


class ProductHomologationQuoteImportWizard(models.TransientModel):
    _name = "product.homologation.quote.import.wizard"
    _inherit = ["product.homologation.import.mixin"]
    _description = "Importar líneas de precotización desde Excel"

    quote_id = fields.Many2one(
        "product.homologation.quote",
        string="Precotización",
        required=True,
        ondelete="cascade",
    )
    match_homologations = fields.Boolean(
        string="Aplicar matching de homologaciones",
        default=True,
        help="Al crear cada línea se busca una homologación validada para el "
             "código del cliente (RF-16).",
    )

    def action_import(self):
        self.ensure_one()
        self._reset_counters()
        _headers, rows = self._read_upload()
        created = skipped = 0
        errors = []
        sequence = max(self.quote_id.line_ids.mapped("sequence") or [10])
        for index, row in enumerate(rows, start=2):
            description = to_text(pick(row, DESCRIPTION_KEYS))
            code = to_text(pick(row, CODE_KEYS))
            if not description:
                errors.append(_("Fila %(row)s: falta la descripción del cliente.")
                              % {"row": index})
                continue
            if not code:
                errors.append(_(
                    "Fila %(row)s: falta el código del cliente; no es posible "
                    "aplicar matching."
                ) % {"row": index})
                continue
            brand_name = to_text(pick(row, BRAND_KEYS))
            competitor = self.env["res.partner"]
            if brand_name:
                competitor = self.env["res.partner"].search(
                    [("name", "=ilike", brand_name)], limit=1
                )
                if not competitor:
                    errors.append(_(
                        "Fila %(row)s: no existe la marca/competidor %(brand)s."
                    ) % {"row": index, "brand": brand_name})
                    continue
            quantity = to_float(pick(row, QUANTITY_KEYS), default=1.0)
            if quantity <= 0:
                errors.append(_("Fila %(row)s: la cantidad debe ser mayor que cero.")
                              % {"row": index})
                continue
            sequence += 10
            values = {
                "quote_id": self.quote_id.id,
                "sequence": sequence,
                "customer_code": code,
                "customer_description": description,
                "competitor_id": competitor.id or False,
                "quantity": quantity,
            }
            price_raw = pick(row, PRICE_KEYS)
            if price_raw not in (None, ""):
                price = to_float(price_raw)
                if price < 0:
                    errors.append(_(
                        "Fila %(row)s: el precio no puede ser negativo."
                    ) % {"row": index})
                    continue
                values["price_unit"] = price
            self.env["product.homologation.quote.line"].create(values)
            created += 1
        return self._finish_import(created, 0, skipped, errors)
