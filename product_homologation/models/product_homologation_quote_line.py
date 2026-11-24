from odoo import api, fields, models, _
from odoo.exceptions import UserError

HOMOLOGATION_LEVELS = [
    ("exact", "Coincidencia exacta"),
    ("near", "Coincidencia cercana"),
    ("approximate", "Coincidencia aproximada"),
    ("best", "Mejor opción"),
]


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
        domain=[("state", "in", ("validated", "provisional"))],
        help="Registro de homologación que vinculó este código al producto interno. "
             "Puede ser una homologación provisional originada en esta misma "
             "precotización.",
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
        help="Homologaciones utilizables cuando el código no identifica una única alternativa.",
    )
    possible_homologation_count = fields.Integer(
        string="Alternativas",
        compute="_compute_possible_homologation_data",
        help="Cantidad de alternativas disponibles para el código, incluyendo la "
             "alternativa ya seleccionada. Se mantiene visible después de elegir.",
    )
    can_open_possible_homologations = fields.Boolean(
        string="Puede abrir alternativas",
        compute="_compute_possible_homologation_data",
    )
    recommended_homologation_id = fields.Many2one(
        "product.homologation",
        string="Alternativa recomendada",
        compute="_compute_possible_homologation_data",
        help="Alternativa sugerida por las reglas de recomendación configuradas. "
             "El vendedor puede cambiarla manualmente.",
    )
    recommendation_reason = fields.Char(
        string="Motivo de la recomendación",
        compute="_compute_possible_homologation_data",
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
            ("provisional", "Provisional"),
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
        digits="Product Price",
        help="Precio editable de la línea. Se inicializa con el precio de lista "
             "del producto asignado, pero el vendedor puede ajustarlo.",
    )
    subtotal = fields.Float(
        string="Subtotal",
        compute="_compute_subtotal",
        store=True,
        digits="Product Price",
        help="Cantidad por precio unitario de la línea.",
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = (line.quantity or 0.0) * (line.price_unit or 0.0)

    @api.depends(
        "customer_code",
        "quote_id",
        "homologation_id",
        "homologation_id.state",
        "possible_homologation_ids",
        "product_id",
    )
    def _compute_possible_homologation_data(self):
        for line in self:
            alternatives = line._get_possible_homologations()
            recommended, reason, _ordered = alternatives._recommend()
            line.possible_homologation_count = len(alternatives)
            line.can_open_possible_homologations = bool(
                len(alternatives) and line.id and isinstance(line.id, int)
            )
            line.recommended_homologation_id = recommended
            line.recommendation_reason = reason

    @api.depends(
        "customer_code",
        "quote_id",
        "homologation_id",
        "homologation_id.state",
        "possible_homologation_ids",
    )
    def _compute_match_status(self):
        for line in self:
            line.match_status = line._get_match_status()

    # ------------------------------------------------------------------
    # Onchange
    # ------------------------------------------------------------------
    @api.onchange("customer_code")
    def _onchange_customer_code(self):
        code = self._normalize_code(self.customer_code)
        if not code:
            self._clear_match()
            self.state = "pending"
            return {}
        matches = self._get_code_homologation_matches()
        usable = matches["usable"]
        if len(usable) == 1:
            self._apply_homologation(usable)
            return {}
        if usable:
            # Varias alternativas: se muestran en la ventana emergente, sin
            # mensaje intrusivo (RF-19) y manteniendo el contador (RF-20).
            self.product_id = False
            self.homologation_id = False
            self.possible_homologation_ids = usable
            self.state = "unmatched"
            return {}
        self._clear_match()
        self.state = "unmatched"
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
            return {}
        if not self._is_usable_homologation(self.homologation_id):
            self.homologation_id = False
            return {
                "warning": {
                    "title": _("Homologación no disponible"),
                    "message": _(
                        "Solo una homologación validada (o una provisional "
                        "originada en esta precotización) puede aplicarse como match."
                    ),
                }
            }
        try:
            self._check_homologation_can_be_applied(self.homologation_id)
        except UserError as error:
            self.homologation_id = False
            return {
                "warning": {
                    "title": _("Homologación incompatible"),
                    "message": str(error),
                }
            }
        self._apply_homologation(self.homologation_id)
        return {}

    @api.onchange("product_id")
    def _onchange_product_id(self):
        self.price_unit = self._price_for_product(self.product_id)
        if self.product_id and self.state != "matched":
            self.state = "matched"
        elif not self.product_id:
            self.state = "pending"
            self.homologation_id = False
            self.possible_homologation_ids = False

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for index, vals in enumerate(vals_list):
            vals = vals.copy()
            if vals.get("customer_code"):
                vals["customer_code"] = vals["customer_code"].strip()
            vals = self._prepare_values_from_homologation(vals)
            if "price_unit" not in vals and vals.get("product_id"):
                vals["price_unit"] = self._price_for_product(
                    self.env["product.product"].browse(vals["product_id"])
                )
            vals_list[index] = vals
        lines = super().create(vals_list)
        lines._reconcile_code_homologations()
        lines._ensure_homologation()
        return lines

    def write(self, vals):
        original_keys = set(vals)
        if vals.get("customer_code"):
            vals = vals.copy()
            vals["customer_code"] = vals["customer_code"].strip()
        if vals.get("homologation_id"):
            vals = self._prepare_values_from_homologation(vals)
        if (
            "product_id" in vals
            and "price_unit" not in vals
            and ("product_id" in original_keys or not any(self.mapped("price_unit")))
        ):
            # Solo se repone el precio de lista si el usuario cambió el
            # producto o la línea aún no tenía precio. Si el producto llega
            # implícito desde una homologación, se conserva el precio editado.
            vals = vals.copy()
            vals["price_unit"] = self._price_for_product(
                self.env["product.product"].browse(vals["product_id"])
            )
        result = super().write(vals)
        if (
            not self.env.context.get("skip_homologation_reconcile")
            and "customer_code" in original_keys
        ):
            self._reconcile_code_homologations()
        if (
            "customer_code" in vals
            or "product_id" in vals
            or "competitor_id" in vals
        ):
            self._ensure_homologation()
        return result

    @api.model
    def _price_for_product(self, product):
        return product.list_price if product else 0.0

    def copy_data(self, default=None):
        """Al duplicar una precotización se vuelve a resolver el match.

        Una homologación provisional solo es utilizable en la precotización
        que la originó (RF-10), por lo que la copia no debe arrastrar la
        referencia de la línea original: el matching se recalcula y, si
        corresponde, se crea/usa la homologación válida del nuevo contexto.
        """
        default = dict(default or {})
        vals_list = super().copy_data(default=default)
        for vals in vals_list:
            vals.pop("homologation_id", None)
            vals.pop("possible_homologation_ids", None)
        return vals_list


    def _prepare_values_from_homologation(self, vals):
        homologation_id = vals.get("homologation_id")
        if not homologation_id:
            return vals
        homologation = self.env["product.homologation"].browse(homologation_id)
        if not self._is_usable_homologation(homologation, self._vals_quote(vals)):
            return vals
        self._check_homologation_can_be_applied(homologation, vals)
        vals = vals.copy()
        vals.setdefault("customer_code", homologation.customer_code)
        vals.setdefault("customer_description", homologation.customer_description)
        vals.setdefault("competitor_id", homologation.competitor_id.id)
        vals.setdefault("product_id", homologation.product_id.id)
        vals.setdefault("state", "matched")
        return vals

    def _vals_quote(self, vals):
        quote_id = vals.get("quote_id")
        if quote_id:
            return self.env["product.homologation.quote"].browse(quote_id)
        if self:
            return self[:1].quote_id
        return self.env["product.homologation.quote"]

    def _normalize_code(self, code):
        return (code or "").strip()

    def _same_code(self, first, second):
        return self._normalize_code(first).casefold() == self._normalize_code(second).casefold()

    def _is_usable_homologation(self, homologation, quote=None):
        """Una homologación es utilizable si está validada o si es provisional
        y fue originada en la misma precotización (RF-10)."""
        if not homologation:
            return False
        if homologation.state == "validated":
            return True
        if homologation.state == "provisional":
            quote = quote or (self[:1].quote_id if self else self.env[
                "product.homologation.quote"
            ])
            return bool(quote and homologation.origin_quote_id == quote)
        return False

    def _check_homologation_values_compatible(self, homologation, code=False, company=False, quote=None):
        if not self._is_usable_homologation(homologation, quote):
            raise UserError(_(
                "Solo una homologación validada, o una provisional originada en "
                "esta precotización, puede aplicarse como match."
            ))
        if company and homologation.company_id and homologation.company_id != company:
            raise UserError(_("La homologación seleccionada pertenece a otra compañía."))
        if code and not self._same_code(code, homologation.customer_code):
            raise UserError(_(
                "La homologación seleccionada no corresponde al código %s. "
                "Use Ver alternativas y seleccione una homologación compatible."
            ) % self._normalize_code(code))

    def _check_homologation_can_be_applied(self, homologation, vals=None):
        vals = vals or {}
        if self:
            for line in self:
                code = vals.get("customer_code", line.customer_code)
                company = line.quote_id.company_id or self.env.company
                line._check_homologation_values_compatible(
                    homologation, code, company, line.quote_id
                )
            return
        quote = self._vals_quote(vals)
        company = (quote.company_id if quote else False) or self.env.company
        self._check_homologation_values_compatible(
            homologation,
            vals.get("customer_code"),
            company,
            quote,
        )

    def _line_matches_homologation(self, homologation, require_validated=False):
        self.ensure_one()
        if not homologation or not self.product_id:
            return False
        if require_validated and not self._is_usable_homologation(homologation):
            return False
        if homologation.product_id != self.product_id:
            return False
        line_code = self._normalize_code(self.customer_code)
        homologation_code = self._normalize_code(homologation.customer_code)
        if line_code or homologation_code:
            return self._same_code(line_code, homologation_code)
        return True

    def _company_domain(self):
        self.ensure_one()
        company = self.quote_id.company_id or self.env.company
        if not company:
            return []
        return ["|", ("company_id", "=", company.id), ("company_id", "=", False)]

    # ------------------------------------------------------------------
    # Búsqueda de homologaciones
    # ------------------------------------------------------------------
    def _get_code_homologations(self):
        self.ensure_one()
        code = self._normalize_code(self.customer_code)
        if not code:
            return self.env["product.homologation"]
        domain = [("customer_code", "=ilike", code)] + self._company_domain()
        return self.env["product.homologation"].search(domain)

    def _get_code_homologation_matches(self):
        homologations = self._get_code_homologations()
        provisional = homologations.filtered(
            lambda hom: hom.state == "provisional"
            and self.quote_id
            and hom.origin_quote_id == self.quote_id
        )
        validated = homologations.filtered(lambda h: h.state == "validated")
        return {
            "validated": validated,
            "provisional": provisional,
            "usable": validated | provisional,
            "draft": homologations.filtered(lambda h: h.state == "draft"),
            "rejected": homologations.filtered(lambda h: h.state == "rejected"),
        }

    def _get_possible_homologations(self):
        """Alternativas utilizables para el código de la línea.

        Se mantiene la lista aun después de seleccionar una alternativa para
        que el contador siga visible (RF-20).
        """
        self.ensure_one()
        if self._normalize_code(self.customer_code):
            return self._get_code_homologation_matches()["usable"]
        return self.possible_homologation_ids.filtered(
            lambda hom: self._is_usable_homologation(hom, self.quote_id)
        )

    def _get_match_status(self):
        self.ensure_one()
        if self.homologation_id:
            if self.homologation_id.state == "validated":
                return "validated"
            if self.homologation_id.state == "provisional":
                return "provisional"
            return self.homologation_id.state
        alternatives = self._get_possible_homologations()
        if len(alternatives) > 1:
            return "alternatives"
        if not self._normalize_code(self.customer_code):
            return "pending"
        matches = self._get_code_homologation_matches()
        if len(matches["usable"]) > 1:
            return "alternatives"
        if matches["usable"]:
            return "validated"
        if matches["draft"]:
            return "draft"
        if matches["rejected"]:
            return "rejected"
        return "unmatched"

    def _is_line_complete(self):
        self.ensure_one()
        return bool(
            self.state == "matched"
            and self.product_id
            and self.homologation_id
            and self._is_usable_homologation(self.homologation_id, self.quote_id)
        )

    def _apply_homologation(self, homologation):
        self.customer_description = homologation.customer_description
        self.competitor_id = homologation.competitor_id
        self.product_id = homologation.product_id
        self.homologation_id = homologation
        # RF-20: las alternativas se mantienen visibles luego de seleccionar.
        self.possible_homologation_ids = self._get_possible_homologations()
        self.state = "matched"

    def _apply_selected_homologation(self, homologation):
        self.ensure_one()
        self._check_homologation_can_be_applied(homologation)
        self.with_context(skip_homologation_reconcile=True).write({
            "homologation_id": homologation.id,
        })

    def _clear_match(self):
        self.product_id = False
        self.homologation_id = False
        self.possible_homologation_ids = False
        self.state = "pending"

    # ------------------------------------------------------------------
    # Reconciliación
    # ------------------------------------------------------------------
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
                if line.possible_homologation_ids:
                    line.with_context(skip_homologation_reconcile=True).write({
                        "possible_homologation_ids": [(5, 0, 0)],
                    })
                continue
            if (
                line.state == "matched"
                and line.product_id
                and line._line_matches_homologation(line.homologation_id)
            ):
                # Mantener el contador de alternativas (RF-20).
                usable = line._get_possible_homologations()
                if set(usable.ids) != set(line.possible_homologation_ids.ids):
                    line.with_context(skip_homologation_reconcile=True).write({
                        "possible_homologation_ids": [(6, 0, usable.ids)],
                    })
                continue
            matches = line._get_code_homologation_matches()
            usable = matches["usable"]
            if len(usable) == 1:
                line.with_context(skip_homologation_reconcile=True).write({
                    "homologation_id": usable.id,
                    "possible_homologation_ids": [(6, 0, usable.ids)],
                })
                continue
            if len(usable) > 1:
                line.with_context(skip_homologation_reconcile=True).write({
                    "product_id": False,
                    "homologation_id": False,
                    "possible_homologation_ids": [(6, 0, usable.ids)],
                    "state": "unmatched",
                })
                continue
            values = {}
            if line.possible_homologation_ids:
                values["possible_homologation_ids"] = [(5, 0, 0)]
            if line.homologation_id and not line._is_usable_homologation(
                line.homologation_id, line.quote_id
            ):
                values.update({"homologation_id": False, "product_id": False})
            if values:
                line.with_context(skip_homologation_reconcile=True).write(values)

    # ------------------------------------------------------------------
    # Homologación provisional (RF-08, RF-09, RF-10)
    # ------------------------------------------------------------------
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
        """Crea una homologación provisional cuando la línea aún no tiene una.

        Las homologaciones creadas desde una precotización quedan en estado
        provisional y solo son utilizables en la precotización que las originó
        hasta que un especialista las valide (RF-09, RF-10).
        """
        for line in self:
            if not line.product_id or not line.customer_description:
                continue
            if line.homologation_id:
                if line._line_matches_homologation(line.homologation_id):
                    continue
                line.homologation_id = False
            existing = line._get_existing_homologations_for_line()
            usable = existing.filtered(
                lambda hom: line._is_usable_homologation(hom, line.quote_id)
            )
            if len(usable) == 1:
                if line.homologation_id != usable:
                    line.homologation_id = usable
                line.state = "matched"
                continue
            if len(usable) > 1:
                line.possible_homologation_ids = usable
                line.state = "unmatched"
                continue
            if existing:
                line.state = "unmatched"
                continue
            homologation = self.env["product.homologation"].create({
                "competitor_id": line.competitor_id.id or False,
                "customer_code": line._normalize_code(line.customer_code) or False,
                "customer_description": line.customer_description,
                "observation": line.observation,
                "product_id": line.product_id.id,
                "state": "provisional",
                "origin_quote_id": line.quote_id.id,
                "origin_quote_line_id": line.id,
            })
            line.homologation_id = homologation
            line.state = "matched"

    # ------------------------------------------------------------------
    # Alternativas
    # ------------------------------------------------------------------
    def action_open_possible_homologations(self):
        self.ensure_one()
        homologations = self._get_possible_homologations()
        tree_view = self.env.ref(
            "product_homologation.view_product_homologation_possible_tree"
        )
        form_view = self.env.ref(
            "product_homologation.view_product_homologation_possible_form"
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Alternativas de homologación"),
            "res_model": "product.homologation",
            "view_mode": "list,form",
            "views": [(tree_view.id, "list"), (form_view.id, "form")],
            "domain": [("id", "in", homologations.ids)],
            "context": {
                "create": False,
                "edit": False,
                "delete": False,
                "homologation_quote_line_id": self.id,
            },
        }

    def action_open_alternatives_wizard(self):
        """Abre la ventana emergente simplificada de alternativas (RF-21)."""
        self.ensure_one()
        wizard = self.env["product.homologation.alternatives.wizard"].create({
            "quote_line_id": self.id,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Seleccionar alternativa de homologación"),
            "res_model": "product.homologation.alternatives.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_apply_recommended(self):
        self.ensure_one()
        recommended = self._get_possible_homologations()._recommend()[0]
        if not recommended:
            raise UserError(_("No hay alternativas para recomendar en esta línea."))
        self._apply_selected_homologation(recommended)
        return self.quote_id.action_open_quote()
