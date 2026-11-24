import logging
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain

_logger = logging.getLogger(__name__)

HOMOLOGATION_LEVELS = [
    ("exact", "Coincidencia exacta"),
    ("near", "Coincidencia cercana"),
    ("approximate", "Coincidencia aproximada"),
    ("best", "Mejor opción"),
]

HOMOLOGATION_LEVEL_PRECISION = {
    "exact": 100.0,
    "near": 90.0,
    "approximate": 80.0,
    "best": 70.0,
}

HOMOLOGATION_STATES = [
    ("draft", "Borrador"),
    ("provisional", "Provisional"),
    ("validated", "Validado"),
    ("rejected", "Rechazado"),
]

SPECIALIST_GROUP = "product_homologation.group_homologation_specialist"


class ProductHomologation(models.Model):
    _name = "product.homologation"
    _description = "Homologación de Productos"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "competitor_id, customer_code"
    _rec_name = "customer_code"

    HOMOLOGATION_LEVEL_PRECISION = HOMOLOGATION_LEVEL_PRECISION

    competitor_id = fields.Many2one(
        "res.partner",
        string="Competidor/Marca",
        domain=[("supplier_rank", ">", 0)],
        help="Marca o competidor al que pertenece el código del cliente. "
             "Ej: Xilong, Johnson, etc.",
    )
    customer_code = fields.Char(
        string="Código del cliente",
        index=True,
        help="Código que usa el cliente/competidor para este producto.",
    )
    customer_description = fields.Text(
        string="Descripción del cliente",
        required=True,
        help="Descripción original del producto tal como la entrega el cliente.",
    )
    observation = fields.Text(
        string="Observación",
        help="Observación interna opcional sobre la homologación.",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto interno",
        required=True,
        domain=[("active", "=", True)],
        help="Producto de Thiemed que equivale al código del cliente.",
    )
    product_default_code = fields.Char(
        related="product_id.default_code",
        string="Código interno",
        readonly=True,
    )
    product_price = fields.Float(
        related="product_id.list_price",
        string="Precio de venta",
        readonly=True,
        help="Precio de lista del producto interno. Se usa en las reglas de recomendación.",
    )
    product_standard_price = fields.Float(
        related="product_id.standard_price",
        string="Costo",
        readonly=True,
        help="Costo del producto interno. Se usa en las reglas de recomendación.",
    )
    homologation_level = fields.Selection(
        HOMOLOGATION_LEVELS,
        string="Nivel de homologación",
        default="exact",
        tracking=True,
        help="Nivel manual de cercanía definido por el validador.",
    )
    precision_pct = fields.Float(
        string="Precisión (%)",
        default=100.0,
        tracking=True,
        help="Porcentaje de precisión de la equivalencia. "
             "Útil cuando no hay match exacto (ej. tijera 14cm vs 16cm).",
    )
    normalized_description = fields.Text(
        string="Descripción normalizada",
        help="Descripción limpia/normalizada para matching futuro por IA. "
             "Se genera automáticamente al guardar.",
        compute="_compute_normalized_description",
        store=True,
    )
    state = fields.Selection(
        HOMOLOGATION_STATES,
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
    )
    validator_id = fields.Many2one(
        "res.users",
        string="Validado por",
        readonly=True,
        tracking=True,
    )
    validation_date = fields.Datetime(
        string="Fecha de validación",
        readonly=True,
        tracking=True,
    )
    origin_quote_id = fields.Many2one(
        "product.homologation.quote",
        string="Precotización de origen",
        readonly=True,
        index=True,
        ondelete="set null",
        help="Precotización desde la cual se creó esta homologación provisional.",
    )
    origin_quote_line_id = fields.Many2one(
        "product.homologation.quote.line",
        string="Línea de origen",
        readonly=True,
        ondelete="set null",
    )
    is_provisional = fields.Boolean(
        string="Es provisional",
        compute="_compute_is_provisional",
        store=True,
    )
    used_in_quote_count = fields.Integer(
        string="Usos en precotizaciones",
        compute="_compute_usage",
    )
    used_in_sale_count = fields.Integer(
        string="Usos en presupuestos",
        compute="_compute_usage",
    )
    is_used = fields.Boolean(
        string="Utilizada",
        compute="_compute_usage",
        help="Indica si la homologación ya fue utilizada en una precotización "
             "o en un presupuesto. Los registros utilizados no se eliminan.",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
    )
    duplicate_homologation_ids = fields.Many2many(
        "product.homologation",
        "product_homologation_duplicate_rel",
        "homologation_id",
        "duplicate_id",
        string="Posibles duplicados",
        help="Otras homologaciones que podrían ser duplicadas de esta.",
        compute="_compute_duplicates",
    )

    _competitor_code_company_uniq = models.Constraint(
        "UNIQUE(competitor_id, customer_code, company_id)",
        "Ya existe una homologación para este competidor con el mismo código.",
    )

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    def _check_unique_competitor_code(self, vals_list):
        """Valida duplicados antes de INSERT para dar un error de usuario.

        La restricción UNIQUE de PostgreSQL se mantiene como última línea de
        defensa, pero validar aquí evita exponer un ``IntegrityError`` crudo
        (y su registro SQL) cuando se crea un código ya existente.
        """
        seen = set()
        for vals in vals_list:
            code = (vals.get("customer_code") or "").strip()
            competitor_id = vals.get("competitor_id")
            if not code or not competitor_id:
                continue
            company_id = vals.get("company_id") or self.env.company.id
            key = (competitor_id, company_id, code.casefold())
            if key in seen:
                raise ValidationError(_(
                    "Ya existe una homologación para este competidor con el "
                    "código %s."
                ) % code)
            seen.add(key)
            duplicate = self.with_context(active_test=False).search([
                ("competitor_id", "=", competitor_id),
                ("company_id", "=", company_id),
                ("customer_code", "=ilike", code),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    "Ya existe una homologación para este competidor con el "
                    "código %s."
                ) % code)

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [dict(vals) for vals in vals_list]
        for vals in vals_list:
            if vals.get("customer_code"):
                vals["customer_code"] = vals["customer_code"].strip()
            if vals.get("homologation_level") and "precision_pct" not in vals:
                vals["precision_pct"] = self._precision_from_level(vals["homologation_level"])
        self._check_unique_competitor_code(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("customer_code"):
            vals = vals.copy()
            vals["customer_code"] = vals["customer_code"].strip()
        if vals.get("homologation_level") and "precision_pct" not in vals:
            vals = vals.copy()
            vals["precision_pct"] = self._precision_from_level(vals["homologation_level"])
        return super().write(vals)

    def unlink(self):
        """Los registros históricos utilizados no se eliminan (RF-13)."""
        used = self.filtered(lambda hom: hom._is_used_record())
        if used:
            raise UserError(_(
                "No se pueden eliminar homologaciones que ya fueron utilizadas "
                "en precotizaciones o presupuestos: %s.\n"
                "Archívelas en su lugar para conservar la trazabilidad."
            ) % ", ".join(used.mapped("display_name")))
        return super().unlink()

    @api.onchange("homologation_level")
    def _onchange_homologation_level(self):
        for rec in self:
            rec.precision_pct = rec._precision_from_level(rec.homologation_level)

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends("state")
    def _compute_is_provisional(self):
        for rec in self:
            rec.is_provisional = rec.state == "provisional"

    def _is_used_record(self):
        self.ensure_one()
        if not self.id:
            return False
        if self.env["product.homologation.quote.line"].sudo().search_count(
            [("homologation_id", "=", self.id)]
        ):
            return True
        return bool(self.env["sale.order.line"].sudo().search_count(
            [("homologation_id", "=", self.id)]
        ))

    @api.depends("customer_code", "product_id")
    def _compute_usage(self):
        QuoteLine = self.env["product.homologation.quote.line"].sudo()
        SaleLine = self.env["sale.order.line"].sudo()
        for rec in self:
            if not isinstance(rec.id, int):
                rec.used_in_quote_count = 0
                rec.used_in_sale_count = 0
                rec.is_used = False
                continue
            rec.used_in_quote_count = QuoteLine.search_count(
                [("homologation_id", "=", rec.id)]
            )
            rec.used_in_sale_count = SaleLine.search_count(
                [("homologation_id", "=", rec.id)]
            )
            rec.is_used = bool(rec.used_in_quote_count or rec.used_in_sale_count)

    @api.depends("customer_code", "competitor_id", "product_id")
    def _compute_duplicates(self):
        for rec in self:
            domains = []
            if rec.customer_code:
                domains.append([("customer_code", "=ilike", rec.customer_code.strip())])
            if rec.product_id:
                domains.append([("product_id", "=", rec.product_id.id)])
            if not domains:
                rec.duplicate_homologation_ids = False
                continue
            domain = Domain.OR(domains)
            if rec.ids:
                domain = Domain.AND([[("id", "not in", rec.ids)], domain])
            rec.duplicate_homologation_ids = self.search(domain, limit=10)

    @api.constrains("competitor_id", "customer_code", "product_id")
    def _check_duplicate_suggestion(self):
        for rec in self:
            if not rec.competitor_id or not rec.customer_code or not rec.product_id:
                continue
            dup = self.search([
                ("id", "!=", rec.id),
                ("competitor_id", "=", rec.competitor_id.id),
                ("customer_code", "=ilike", rec.customer_code.strip()),
                ("product_id", "!=", rec.product_id.id),
            ], limit=1)
            if dup:
                _logger.info(
                    "Homologación %s: mismo código %s para competidor %s "
                    "pero distinto producto interno (%s vs %s)",
                    rec.id, rec.customer_code, rec.competitor_id.display_name,
                    rec.product_id.display_name, dup.product_id.display_name,
                )

    @api.depends("customer_description")
    def _compute_normalized_description(self):
        for rec in self:
            rec.normalized_description = rec._normalize(rec.customer_description)

    @api.onchange("customer_description")
    def _onchange_normalize_description(self):
        if self.customer_description:
            self.normalized_description = self._normalize(self.customer_description)

    def _normalize(self, text):
        if not text:
            return ""
        t = text.lower().strip()
        t = re.sub(r"[^a-z0-9áéíóúüñ\s]", " ", t)
        t = re.sub(r"\s+", " ", t)
        return t.strip()

    def _precision_from_level(self, level):
        return self.HOMOLOGATION_LEVEL_PRECISION.get(level or "exact", 0.0)

    # ------------------------------------------------------------------
    # Búsqueda / autocompletado (RF-33)
    # ------------------------------------------------------------------
    @api.model
    @api.readonly
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        """Autocompletado por código, descripción o código interno.

        Además de buscar por el nombre mostrado (código del cliente), se busca
        por descripción del cliente y por código/nombre del producto interno,
        de modo que el vendedor pueda escribir el código que recuerda.
        """
        domain = list(domain or [])
        if not name:
            return super().name_search(name, domain, operator, limit)
        extra = Domain.OR([
            [("customer_code", operator, name)],
            [("customer_description", operator, name)],
            [("product_id.default_code", operator, name)],
            [("product_id.name", operator, name)],
        ])
        records = self.search(Domain.AND([domain, extra]), limit=limit)
        return [(record.id, record.display_name) for record in records.sudo()]

    @api.model
    def _get_code_suggestions(self, code, limit=10):
        """Sugerencias para un código de cliente mientras se escribe (RF-33).

        Devuelve primero las homologaciones validadas y luego las provisionales,
        borradores y rechazadas.
        """
        code = (code or "").strip()
        if not code:
            return self.browse()
        domain = [
            "|", "|",
            ("customer_code", "=ilike", f"{code}%"),
            ("customer_code", "=ilike", f"%{code}%"),
            ("product_id.default_code", "=ilike", f"%{code}%"),
        ]
        records = self.search(domain, limit=limit)
        priority = {"validated": 0, "provisional": 1, "draft": 2, "rejected": 3}
        return records.sorted(
            key=lambda hom: (priority.get(hom.state, 9), hom.customer_code or "")
        )

    # ------------------------------------------------------------------
    # Flujo de estados (RF-05, RF-06, RF-09, RF-10)
    # ------------------------------------------------------------------
    def _check_specialist(self):
        if self.env.is_admin() or self.env.user.has_group(SPECIALIST_GROUP):
            return True
        raise UserError(_(
            "Solo un especialista de homologación puede validar, rechazar "
            "o devolver a borrador una homologación."
        ))

    def action_validate(self):
        self._check_specialist()
        self.write({
            "state": "validated",
            "validator_id": self.env.user.id,
            "validation_date": fields.Datetime.now(),
        })
        self.env[
            "product.homologation.quote.line"
        ]._reconcile_after_homologation_validation(self)

    def action_reject(self):
        self._check_specialist()
        self.write({
            "state": "rejected",
            "validator_id": self.env.user.id,
            "validation_date": fields.Datetime.now(),
        })

    def action_draft(self):
        self._check_specialist()
        self.write({
            "state": "draft",
            "validator_id": False,
            "validation_date": False,
        })

    def action_send_to_validation(self):
        """Marca un borrador como provisional (pendiente de validación)."""
        self.write({"state": "provisional"})

    def action_find_cross_homologations(self):
        self.ensure_one()
        if not self.product_id:
            return
        domain = [
            ("product_id", "=", self.product_id.id),
            ("id", "!=", self.id),
            ("state", "=", "validated"),
        ]
        cross = self.search(domain)
        if not cross:
            return {"type": "ir.actions.act_window_close"}
        return {
            "type": "ir.actions.act_window",
            "name": "Homologaciones cruzadas",
            "res_model": "product.homologation",
            "domain": [("id", "in", cross.ids)],
            "view_mode": "list,form",
        }

    def action_apply_to_quote_line(self):
        self.ensure_one()
        quote_line_id = self.env.context.get("homologation_quote_line_id")
        if not quote_line_id:
            raise UserError(_("No hay una línea de precotización activa."))
        line = self.env["product.homologation.quote.line"].browse(quote_line_id).exists()
        if not line:
            raise UserError(_("La línea de precotización ya no existe."))
        line._apply_selected_homologation(self)
        return line.quote_id.action_open_quote()

    def action_view_quotes(self):
        self.ensure_one()
        lines = self.env["product.homologation.quote.line"].search(
            [("homologation_id", "=", self.id)]
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Precotizaciones que usan esta homologación"),
            "res_model": "product.homologation.quote",
            "view_mode": "list,form",
            "domain": [("id", "in", lines.quote_id.ids)],
        }

    # ------------------------------------------------------------------
    # Reglas de recomendación (RF-23, RF-24, RF-25)
    # ------------------------------------------------------------------
    @api.model
    def _get_recommendation_rules(self):
        return self.env["product.homologation.rule"].search(
            [
                ("active", "=", True),
                "|",
                ("company_id", "=", False),
                ("company_id", "=", self.env.company.id),
            ],
            order="priority, id",
        )

    def _sort_for_rules(self, rules):
        """Ordena el recordset aplicando las reglas configuradas.

        Se aplica un ordenamiento estable desde la regla de menor prioridad
        (mayor número) hasta la de mayor prioridad, de modo que la última
        regla aplicada (mayor prioridad) domine el resultado.
        """
        records = self
        if not records:
            return records
        for rule in reversed(rules):
            records = records.sorted(key=rule._sort_key)
        return records

    def _recommend(self):
        """Devuelve (homologación recomendada, motivo, ordenadas)."""
        rules = self._get_recommendation_rules()
        ordered = self._sort_for_rules(rules)
        if not ordered:
            return self.browse(), "", ordered
        best = ordered[0]
        reason = ""
        for rule in rules:
            best_key = rule._sort_key(best)
            if all(best_key <= rule._sort_key(other) for other in ordered):
                if len(ordered) == 1 or best_key != rule._sort_key(ordered[1]):
                    reason = rule.name
                    break
        if not reason:
            reason = _("Mayor precisión, menor precio y orden de registro")
        return best, reason, ordered
