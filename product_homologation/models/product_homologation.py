import logging
import re

from odoo import fields, models, api

_logger = logging.getLogger(__name__)


class ProductHomologation(models.Model):
    _name = "product.homologation"
    _description = "Homologación de Productos"
    _order = "competitor_id, customer_code"
    _rec_name = "customer_code"

    competitor_id = fields.Many2one(
        "res.partner",
        string="Competidor/Marca",
        required=True,
        domain=[("supplier_rank", ">", 0)],
        help="Marca o competidor al que pertenece el código del cliente. "
             "Ej: Xilong, Johnson, etc.",
    )
    customer_code = fields.Char(
        string="Código del cliente",
        required=True,
        index=True,
        help="Código que usa el cliente/competidor para este producto.",
    )
    customer_description = fields.Text(
        string="Descripción del cliente",
        help="Descripción original del producto tal como la entrega el cliente.",
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
    precision_pct = fields.Float(
        string="Precisión (%)",
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
    )
    validator_id = fields.Many2one(
        "res.users",
        string="Validado por",
        readonly=True,
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

    @api.depends("customer_code", "competitor_id", "product_id")
    def _compute_duplicates(self):
        for rec in self:
            domain = [
                ("id", "!=", rec.id),
                "|",
                ("competitor_id", "=", rec.competitor_id.id),
                ("customer_code", "=", rec.customer_code),
            ]
            if rec.product_id:
                domain = [
                    ("id", "!=", rec.id),
                    "|",
                    "&",
                    ("competitor_id", "=", rec.competitor_id.id),
                    ("customer_code", "=", rec.customer_code),
                    "&",
                    ("product_id", "=", rec.product_id.id),
                    ("customer_code", "=", rec.customer_code),
                ]
            rec.duplicate_homologation_ids = self.search(domain, limit=10)

    @api.constrains("competitor_id", "customer_code", "product_id")
    def _check_duplicate_suggestion(self):
        for rec in self:
            dup = self.search([
                ("id", "!=", rec.id),
                ("competitor_id", "=", rec.competitor_id.id),
                ("customer_code", "=", rec.customer_code),
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
        self.state = "validated"
        self.validator_id = self.env.user

    def action_reject(self):
        self.state = "rejected"
        self.validator_id = self.env.user

    def action_draft(self):
        self.state = "draft"
        self.validator_id = False

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
