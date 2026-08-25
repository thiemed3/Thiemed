import logging
import re

from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.osv import expression

_logger = logging.getLogger(__name__)


class ProductHomologation(models.Model):
    _name = "product.homologation"
    _description = "Homologación de Productos"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "competitor_id, customer_code"
    _rec_name = "customer_code"

    HOMOLOGATION_LEVEL_PRECISION = {
        "exact": 100.0,
        "near": 90.0,
        "approximate": 80.0,
        "best": 70.0,
    }

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
    homologation_level = fields.Selection(
        [
            ("exact", "Coincidencia exacta"),
            ("near", "Coincidencia cercana"),
            ("approximate", "Coincidencia aproximada"),
            ("best", "Mejor opción"),
        ],
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
        [("draft", "Borrador"), ("validated", "Validado"), ("rejected", "Rechazado")],
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

    _sql_constraints = [
        (
            "uniq_competitor_code",
            "unique(competitor_id, customer_code, company_id)",
            "Ya existe una homologación para este competidor con el mismo código.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("customer_code"):
                vals["customer_code"] = vals["customer_code"].strip()
            if vals.get("homologation_level") and "precision_pct" not in vals:
                vals["precision_pct"] = self._precision_from_level(vals["homologation_level"])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("customer_code"):
            vals = vals.copy()
            vals["customer_code"] = vals["customer_code"].strip()
        if vals.get("homologation_level") and "precision_pct" not in vals:
            vals = vals.copy()
            vals["precision_pct"] = self._precision_from_level(vals["homologation_level"])
        return super().write(vals)

    @api.onchange("homologation_level")
    def _onchange_homologation_level(self):
        for rec in self:
            rec.precision_pct = rec._precision_from_level(rec.homologation_level)

    def _precision_from_level(self, level):
        return self.HOMOLOGATION_LEVEL_PRECISION.get(level or "exact", 0.0)

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
            domain = expression.OR(domains)
            if rec.ids:
                domain = [("id", "not in", rec.ids)] + domain
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

    @api.onchange("customer_description")
    def _onchange_normalize_description(self):
        if self.customer_description:
            self.normalized_description = self._normalize(self.customer_description)

    @api.depends("customer_description")
    def _compute_normalized_description(self):
        for rec in self:
            rec.normalized_description = self._normalize(rec.customer_description)

    def _normalize(self, text):
        if not text:
            return ""
        t = text.lower().strip()
        t = re.sub(r"[^a-z0-9áéíóúüñ\s]", " ", t)
        t = re.sub(r"\s+", " ", t)
        return t.strip()

    def action_validate(self):
        self.write({"state": "validated", "validator_id": self.env.user.id})
        self.env[
            "product.homologation.quote.line"
        ]._reconcile_after_homologation_validation(self)

    def action_reject(self):
        self.write({"state": "rejected", "validator_id": self.env.user.id})

    def action_draft(self):
        self.write({"state": "draft", "validator_id": False})

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
