from odoo import fields, models, api, _


class ProductHomologationQuoteLine(models.Model):
    _name = "product.homologation.quote.line"
    _description = "Línea de precotización"
    _order = "quote_id, sequence, id"

    quote_id = fields.Many2one(
        "product.homologation.quote",
        string="Precotización",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(string="Secuencia", default=10)
    customer_code = fields.Char(
        string="Código del cliente",
        help="Código original del producto según el listado del cliente.",
    )
    competitor_id = fields.Many2one(
        "res.partner",
        string="Competidor/Marca",
        domain=[("supplier_rank", ">", 0)],
        help="Marca o competidor informado por el cliente para esta línea.",
    )
    customer_description = fields.Text(
        string="Descripción del cliente",
        required=True,
        help="Descripción original del producto.",
    )
    observation = fields.Text(string="Observación")
    product_id = fields.Many2one(
        "product.product",
        string="Producto interno",
        domain=[("active", "=", True)],
        help="Producto de Thiemed sugerido como homólogo.",
    )
    homologation_id = fields.Many2one(
        "product.homologation",
        string="Homologación aplicada",
        domain=[("state", "=", "validated")],
        help="Registro de homologación que vinculó este código al producto interno.",
    )
    homologation_state = fields.Selection(
        related="homologation_id.state",
        string="Estado homologación",
        readonly=True,
    )
    homologation_create_uid = fields.Many2one(
        "res.users",
        related="homologation_id.create_uid",
        string="Homologación creada por",
        readonly=True,
    )
    homologation_validator_id = fields.Many2one(
        "res.users",
        related="homologation_id.validator_id",
        string="Validador homologación",
        readonly=True,
    )
    homologation_level = fields.Selection(
        related="homologation_id.homologation_level",
        string="Nivel homologación",
        readonly=True,
    )
    homologation_precision_pct = fields.Float(
        related="homologation_id.precision_pct",
        string="Precisión homologación (%)",
        readonly=True,
    )
    homologation_observation = fields.Text(
        related="homologation_id.observation",
        string="Observación homologación",
        readonly=True,
    )
    possible_homologation_ids = fields.Many2many(
        "product.homologation",
        "product_homologation_quote_line_possible_rel",
        "quote_line_id",
        "homologation_id",
        string="Alternativas de homologación",
        help="Homologaciones validadas posibles cuando el código no identifica una única alternativa.",
    )
    possible_homologation_count = fields.Integer(
        string="Alternativas",
        compute="_compute_possible_homologation_count",
    )
    state = fields.Selection(
        [("pending", "Pendiente"), ("matched", "Producto asignado"), ("unmatched", "Sin match")],
        string="Estado técnico",
        default="pending",
        required=True,
    )
    match_status = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("validated", "Validada"),
            ("alternatives", "Varias alternativas"),
            ("draft", "Borrador existente"),
            ("rejected", "Rechazada existente"),
            ("unmatched", "Sin homologación"),
        ],
        string="Estado match",
        compute="_compute_match_status",
    )
    quantity = fields.Float(string="Cantidad", default=1.0, required=True)
    price_unit = fields.Float(
        string="Precio unitario",
        compute="_compute_price_unit",
        readonly=False,
        store=True,
        precompute=True,
    )

    @api.depends("product_id")
    def _compute_price_unit(self):
        for line in self:
            if line.product_id:
                line.price_unit = line.product_id.list_price
            else:
                line.price_unit = 0.0

    @api.depends("possible_homologation_ids")
    def _compute_possible_homologation_count(self):
        for line in self:
            line.possible_homologation_count = len(line.possible_homologation_ids)

    @api.depends(
        "customer_code",
        "homologation_id",
        "homologation_id.state",
        "possible_homologation_ids",
    )
    def _compute_match_status(self):
        for line in self:
            line.match_status = line._get_match_status()

    @api.onchange("customer_code")
    def _onchange_customer_code(self):
        code = self._normalize_code(self.customer_code)
        if not code:
            self.possible_homologation_ids = False
            if not self.product_id:
                self.state = "pending"
            return
        matches = self._get_code_homologation_matches()
        validated = matches["validated"]
        if len(validated) == 1:
            self._apply_homologation(validated)
            return

        self.product_id = False
        self.homologation_id = False
        self.possible_homologation_ids = validated if len(validated) > 1 else False
        self.state = "unmatched"
        if len(validated) > 1:
            return {
                "domain": {"homologation_id": [("id", "in", validated.ids)]},
                "warning": {
                    "title": _("Múltiples homologaciones"),
                    "message": _(
                        "Existen %s homologaciones validadas para este código. "
                        "Seleccione una alternativa manualmente."
                    ) % len(validated),
                }
            }
        if matches["draft"] or matches["rejected"]:
            return {
                "warning": {
                    "title": _("Sin homologación validada"),
                    "message": _(
                        "No existe una homologación validada para este código. "
                        "Se encontraron %s en borrador y %s rechazadas."
                    ) % (len(matches["draft"]), len(matches["rejected"])),
                }
            }
        return {
            "warning": {
                "title": _("Sin coincidencia"),
                "message": _("No existe una homologación validada para este código."),
            }
            }

    @api.onchange("homologation_id")
    def _onchange_homologation_id(self):
        if not self.homologation_id:
            return
        if self.homologation_id.state != "validated":
            return {
                "warning": {
                    "title": _("Homologación no validada"),
                    "message": _(
                        "Solo una homologación validada puede aplicarse como match."
                    ),
                }
            }
        self._apply_homologation(self.homologation_id)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id and self.state != "matched":
            self.state = "matched"
        elif not self.product_id:
            self.state = "pending"
            self.homologation_id = False
            self.possible_homologation_ids = False

    @api.model_create_multi
    def create(self, vals_list):
        for index, vals in enumerate(vals_list):
            vals = vals.copy()
            if vals.get("customer_code"):
                vals["customer_code"] = vals["customer_code"].strip()
            vals_list[index] = self._prepare_values_from_homologation(vals)
        lines = super().create(vals_list)
        lines._ensure_homologation()
        return lines

    def write(self, vals):
        if vals.get("customer_code"):
            vals = vals.copy()
            vals["customer_code"] = vals["customer_code"].strip()
        if vals.get("homologation_id"):
            vals = self._prepare_values_from_homologation(vals)
        result = super().write(vals)
        if (
            "customer_code" in vals
            or "product_id" in vals
            or "competitor_id" in vals
        ):
            self._ensure_homologation()
        return result

    def _prepare_values_from_homologation(self, vals):
        homologation_id = vals.get("homologation_id")
        if not homologation_id:
            return vals
        homologation = self.env["product.homologation"].browse(homologation_id)
        if not homologation or homologation.state != "validated":
            return vals
        vals = vals.copy()
        vals.setdefault("customer_code", homologation.customer_code)
        vals.setdefault("customer_description", homologation.customer_description)
        vals.setdefault("competitor_id", homologation.competitor_id.id)
        vals.setdefault("product_id", homologation.product_id.id)
        vals.setdefault("state", "matched")
        return vals

    def _normalize_code(self, code):
        return (code or "").strip()

    def _company_domain(self):
        self.ensure_one()
        company = self.quote_id.company_id or self.env.company
        if not company:
            return []
        return ["|", ("company_id", "=", company.id), ("company_id", "=", False)]

    def _get_code_homologations(self):
        self.ensure_one()
        code = self._normalize_code(self.customer_code)
        if not code:
            return self.env["product.homologation"]
        domain = [("customer_code", "=ilike", code)] + self._company_domain()
        return self.env["product.homologation"].search(domain)

    def _get_code_homologation_matches(self):
        homologations = self._get_code_homologations()
        return {
            "validated": homologations.filtered(lambda h: h.state == "validated"),
            "draft": homologations.filtered(lambda h: h.state == "draft"),
            "rejected": homologations.filtered(lambda h: h.state == "rejected"),
        }

    def _get_match_status(self):
        self.ensure_one()
        if self.homologation_id:
            if self.homologation_id.state == "validated":
                return "validated"
            return self.homologation_id.state
        if self.possible_homologation_ids:
            return "alternatives"
        if not self._normalize_code(self.customer_code):
            return "pending"
        matches = self._get_code_homologation_matches()
        if len(matches["validated"]) > 1:
            return "alternatives"
        if matches["validated"]:
            return "validated"
        if matches["draft"]:
            return "draft"
        if matches["rejected"]:
            return "rejected"
        return "unmatched"

    def _apply_homologation(self, homologation):
        self.customer_description = homologation.customer_description
        self.competitor_id = homologation.competitor_id
        self.product_id = homologation.product_id
        self.homologation_id = homologation
        self.possible_homologation_ids = False
        self.state = "matched"

    @api.model
    def _reconcile_after_homologation_validation(self, homologations):
        lines = self.browse()
        for homologation in homologations.filtered(lambda h: h.state == "validated"):
            code = self._normalize_code(homologation.customer_code)
            if not code:
                continue
            lines |= self.search([("customer_code", "=ilike", code)])
        lines._reconcile_code_homologations()

    def _reconcile_code_homologations(self):
        for line in self:
            if not line._normalize_code(line.customer_code):
                continue
            if (
                line.state == "matched"
                and line.product_id
                and line.homologation_id.state == "validated"
                and line.product_id == line.homologation_id.product_id
            ):
                if line.possible_homologation_ids:
                    line.possible_homologation_ids = False
                continue
            matches = line._get_code_homologation_matches()
            validated = matches["validated"]
            if len(validated) == 1:
                line.write({
                    "homologation_id": validated.id,
                    "possible_homologation_ids": [(5, 0, 0)],
                })
                continue
            if len(validated) > 1:
                line.write({
                    "product_id": False,
                    "homologation_id": False,
                    "possible_homologation_ids": [(6, 0, validated.ids)],
                    "state": "unmatched",
                })

    def _get_existing_homologations_for_line(self):
        self.ensure_one()
        code = self._normalize_code(self.customer_code)
        if not code or not self.product_id:
            return self.env["product.homologation"]
        domain = [
            ("customer_code", "=ilike", code),
            ("product_id", "=", self.product_id.id),
        ] + self._company_domain()
        if self.competitor_id:
            domain.append(("competitor_id", "=", self.competitor_id.id))
        return self.env["product.homologation"].search(domain)

    def _ensure_homologation(self):
        for line in self:
            if not line.product_id or not line.customer_description:
                continue
            if line.homologation_id:
                if line.homologation_id.product_id == line.product_id:
                    continue
                line.homologation_id = False
            existing = line._get_existing_homologations_for_line()
            validated = existing.filtered(lambda h: h.state == "validated")
            if len(validated) == 1:
                if line.homologation_id != validated:
                    line.homologation_id = validated
                continue
            if len(validated) > 1:
                line.possible_homologation_ids = validated
                line.state = "unmatched"
                continue
            if existing:
                line.state = "unmatched"
                continue
            hom = self.env["product.homologation"].create({
                "competitor_id": line.competitor_id.id or False,
                "customer_code": line._normalize_code(line.customer_code) or False,
                "customer_description": line.customer_description,
                "observation": line.observation,
                "product_id": line.product_id.id,
                "state": "draft",
            })
            line.homologation_id = hom

    def action_open_possible_homologations(self):
        self.ensure_one()
        homologations = self.possible_homologation_ids
        if not homologations and self._normalize_code(self.customer_code):
            homologations = self._get_code_homologation_matches()["validated"]
        return {
            "type": "ir.actions.act_window",
            "name": _("Alternativas de homologación"),
            "res_model": "product.homologation",
            "view_mode": "list,form",
            "domain": [("id", "in", homologations.ids)],
            "context": {"create": False},
        }
