from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProductHomologationQuote(models.Model):
    _name = "product.homologation.quote"
    _description = "Precotización de homologación"
    _order = "id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"

    name = fields.Char(string="Referencia", required=True, index=True, default="Nuevo")
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        required=True,
        domain=[("active", "=", True)],
        tracking=True,
    )
    line_ids = fields.One2many(
        "product.homologation.quote.line",
        "quote_id",
        string="Líneas",
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("in_progress", "En progreso"),
            ("homologated", "Homologado"),
            ("converted", "Convertido a presupuesto"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Presupuesto generado",
        readonly=True,
        tracking=True,
    )
    # Versionado (RF-32)
    parent_id = fields.Many2one(
        "product.homologation.quote",
        string="Versión anterior",
        readonly=True,
        index=True,
        ondelete="set null",
    )
    root_id = fields.Many2one(
        "product.homologation.quote",
        string="Precotización original",
        readonly=True,
        index=True,
        ondelete="set null",
    )
    version = fields.Integer(string="Versión", default=1, readonly=True)
    version_count = fields.Integer(
        string="Cantidad de versiones",
        compute="_compute_version_count",
    )
    # Totales (RF-26, RF-27, RF-28)
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        default=lambda self: self.env.company.currency_id,
    )
    total_quantity = fields.Float(
        string="Total de piezas",
        compute="_compute_totals",
        store=True,
        digits="Product Unit of Measure",
        help="Suma de las cantidades de todas las líneas de la precotización.",
    )
    total_amount = fields.Monetary(
        string="Total precotización",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
        help="Suma de cantidad por precio unitario de todas las líneas.",
    )
    global_precision = fields.Float(
        string="Precisión global (%)",
        compute="_compute_totals",
        store=True,
        help="Indicador global de precisión ponderado por el valor de cada línea. "
             "Las líneas sin homologación no aportan precisión.",
    )
    price_review_count = fields.Integer(
        string="Precios a revisar",
        compute="_compute_price_review_count",
        help="Líneas cuyo precio unitario difiere del precio de lista del "
             "producto interno al momento de la revisión.",
    )
    line_count = fields.Integer(
        string="Nº de líneas",
        compute="_compute_line_count",
    )
    matched_count = fields.Integer(
        string="Homologadas",
        compute="_compute_line_count",
    )
    provisional_count = fields.Integer(
        string="Provisionales",
        compute="_compute_line_count",
        help="Líneas que usan una homologación provisional pendiente de validación.",
    )
    notes = fields.Text(string="Notas")
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
    )

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "name" not in vals or vals.get("name") == "Nuevo":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("product.homologation.quote")
                    or "Nuevo"
                )
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends("line_ids.subtotal", "line_ids.quantity", "line_ids.price_unit")
    def _compute_totals(self):
        for quote in self:
            lines = quote.line_ids
            quote.total_quantity = sum(lines.mapped("quantity"))
            quote.total_amount = sum(lines.mapped("subtotal"))
            base = sum(
                line.subtotal for line in lines if line.product_id and line.subtotal
            )
            if base:
                quote.global_precision = sum(
                    (line.homologation_precision_pct or 0.0) * line.subtotal
                    for line in lines
                    if line.product_id
                ) / base
            else:
                precisions = [
                    line.homologation_precision_pct
                    for line in lines
                    if line.homologation_id and line.homologation_id.state == "validated"
                ]
                quote.global_precision = (
                    sum(precisions) / len(precisions) if precisions else 0.0
                )

    @api.depends("line_ids.price_unit", "line_ids.product_id", "line_ids.quantity")
    def _compute_price_review_count(self):
        for quote in self:
            quote.price_review_count = len(quote._get_price_review_lines())

    @api.depends(
        "line_ids.state",
        "line_ids.product_id",
        "line_ids.homologation_id",
        "line_ids.homologation_id.state",
    )
    def _compute_line_count(self):
        for q in self:
            lines = q.line_ids
            q.line_count = len(lines)
            q.matched_count = len(lines.filtered(
                lambda line: line.state == "matched"
                and line.product_id
                and line.homologation_id
                and line.homologation_id.state == "validated"
            ))
            q.provisional_count = len(lines.filtered(
                lambda line: line.homologation_id
                and line.homologation_id.state == "provisional"
            ))

    def _compute_version_count(self):
        for quote in self:
            if not isinstance(quote.id, int):
                quote.version_count = 1
                continue
            root = quote.root_id or quote
            quote.version_count = self.search_count([
                "|", ("id", "=", root.id), ("root_id", "=", root.id),
            ])

    # ------------------------------------------------------------------
    # Líneas y validaciones
    # ------------------------------------------------------------------
    def action_open_quote(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "product.homologation.quote",
            "view_mode": "form",
            "res_id": self.id,
        }

    def _get_incomplete_lines(self):
        """Líneas que no tienen producto ni homologación utilizable."""
        return self.line_ids.filtered(lambda line: not line._is_line_complete())

    def _get_unvalidated_lines(self):
        return self.line_ids.filtered(
            lambda line: line.homologation_id
            and line.homologation_id.state == "provisional"
        )

    def _check_lines_ready_for_sale(self):
        for quote in self:
            incomplete_lines = quote._get_incomplete_lines()
            if incomplete_lines:
                raise UserError(_(
                    "No se puede continuar: quedan %s línea(s) pendientes de homologar. "
                    "Todas las líneas deben tener producto y homologación utilizable."
                ) % len(incomplete_lines))

    def _check_provisional_lines_validated(self):
        for quote in self:
            provisional = quote._get_unvalidated_lines()
            if provisional:
                raise UserError(_(
                    "No se puede generar el presupuesto: %s línea(s) usan una "
                    "homologación provisional pendiente de validación por un "
                    "especialista.\n"
                    "Solicite la validación o reemplace esas homologaciones antes "
                    "de convertir la precotización."
                ) % len(provisional))

    def action_confirm_homologation(self):
        """Homologar todo (RF-M06).

        Las homologaciones provisionales originadas en esta precotización se
        aceptan para dejarla homologada (RF-10); la conversión a presupuesto
        exige que el especialista las valide.
        """
        self._check_lines_ready_for_sale()
        self.state = "homologated"

    def action_cancel(self):
        self.state = "cancelled"

    def action_draft(self):
        self.state = "draft"

    def action_set_in_progress(self):
        self.state = "in_progress"

    def action_import_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Importar líneas de precotización"),
            "res_model": "product.homologation.quote.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_quote_id": self.id},
        }

    # ------------------------------------------------------------------
    # Precio (RF-31)
    # ------------------------------------------------------------------
    def _get_price_review_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda line: line.product_id
            and abs((line.price_unit or 0.0) - (line.product_id.list_price or 0.0)) > 0.01
        )

    def _get_price_review_message(self):
        self.ensure_one()
        lines = self._get_price_review_lines()
        if not lines:
            return ""
        details = _(
            "Revisión de precios: %(count)s línea(s) mantienen un precio distinto "
            "al de lista del producto. Se conserva el precio de la precotización."
        ) % {"count": len(lines)}
        rows = [
            _("- %(code)s / %(product)s: precotización %(quote_price).2f, lista %(list_price).2f")
            % {
                "code": line.customer_code or _("Sin código"),
                "product": line.product_id.display_name,
                "quote_price": line.price_unit,
                "list_price": line.product_id.list_price,
            }
            for line in lines
        ]
        return "\n".join([details] + rows)

    # ------------------------------------------------------------------
    # Conversión a presupuesto (RF-M08, RF-30, RF-31)
    # ------------------------------------------------------------------
    def action_convert_to_sale(self):
        self.ensure_one()
        if self.state == "converted" or self.sale_order_id:
            raise UserError(_(
                "Esta precotización ya fue convertida a presupuesto. "
                "No se puede crear un segundo presupuesto."
            ))
        self._check_lines_ready_for_sale()
        self._check_provisional_lines_validated()
        SaleOrder = self.env["sale.order"]
        order_vals = {
            "partner_id": self.partner_id.id,
            "origin": self.name,
            "homologation_quote_id": self.id,
        }
        if "homologation_lead_id" in SaleOrder._fields and "lead_id" in self._fields:
            order_vals["homologation_lead_id"] = self.lead_id.id
        # Compatibilidad con bases que tengan instalado sale_crm.
        if "opportunity_id" in SaleOrder._fields and "lead_id" in self._fields:
            order_vals["opportunity_id"] = self.lead_id.id
        order = SaleOrder.create(order_vals)
        SaleLine = self.env["sale.order.line"]
        for line in self.line_ids:
            code = line.customer_code or _("Sin código")
            homologation_code = line.homologation_id.customer_code or _("Sin código")
            values = {
                "order_id": order.id,
                "product_id": line.product_id.id,
                "product_uom_qty": line.quantity,
                # Se conserva el precio editado en la precotización (RF-31).
                "price_unit": line.price_unit,
                "name": self._prepare_sale_line_name(line, code, homologation_code),
                "homologation_customer_code": line.customer_code,
                "homologation_customer_description": line.customer_description,
                "homologation_observation": line.homologation_id.observation,
                "homologation_quote_observation": line.observation,
                "homologation_level": line.homologation_id.homologation_level,
                "homologation_precision_pct": line.homologation_id.precision_pct,
                "homologation_quote_line_id": line.id,
                "homologation_id": line.homologation_id.id,
                "homologation_quote_id": self.id,
            }
            SaleLine.create(values)
        self.sale_order_id = order.id
        self.state = "converted"
        price_message = self._get_price_review_message()
        if price_message:
            order.message_post(
                body="<p>%s</p>" % price_message.replace("\n", "<br/>"),
                subtype_xmlid="mail.mt_note",
            )
            self.message_post(
                body="<p>%s</p>" % price_message.replace("\n", "<br/>"),
                subtype_xmlid="mail.mt_note",
            )
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": order.id,
        }

    def _prepare_sale_line_name(self, line, code, homologation_code):
        level = line.homologation_id.homologation_level
        level_label = dict(
            line.homologation_id._fields["homologation_level"].selection
        ).get(level, _("Sin nivel"))
        precision = "%g" % (line.homologation_id.precision_pct or 0.0)
        name_parts = [
            f"[{code}] {line.customer_description}",
            f"Homologación: {homologation_code} -> {line.product_id.display_name}",
            _("Nivel: %s (%s%%)") % (level_label, precision),
        ]
        if line.homologation_id.observation:
            name_parts.append(_("Obs. homologación: %s") % line.homologation_id.observation)
        if line.observation:
            name_parts.append(_("Obs. precotización: %s") % line.observation)
        return "\n".join(name_parts)

    # ------------------------------------------------------------------
    # Duplicación y versionado (RF-32)
    # ------------------------------------------------------------------
    def action_duplicate(self):
        self.ensure_one()
        root = self.root_id or self
        if not root.root_id:
            root.root_id = root.id
        siblings = self.search(["|", ("id", "=", root.id), ("root_id", "=", root.id)])
        version = max(siblings.mapped("version") or [1]) + 1
        new_quote = self.copy({
            "name": "Nuevo",
            "state": "draft",
            "sale_order_id": False,
            "parent_id": self.id,
            "root_id": root.id,
            "version": version,
        })
        # En Odoo 19 los One2many no se copian automáticamente. Las líneas se
        # recrean explícitamente para volver a resolver el match en el contexto
        # de la nueva versión (RF-32, RF-10).
        line_model = self.env["product.homologation.quote.line"]
        line_vals_list = []
        for line in self.line_ids:
            vals = line.copy_data()[0]
            vals["quote_id"] = new_quote.id
            vals.pop("possible_homologation_ids", None)
            if not line._is_usable_homologation(line.homologation_id, new_quote):
                vals.pop("homologation_id", None)
                vals["product_id"] = False
                vals["state"] = "unmatched"
            line_vals_list.append(vals)
        if line_vals_list:
            line_model.create(line_vals_list)
        self.message_post(
            body=_("Precotización duplicada como %s (versión %s).")
            % (new_quote.name, new_quote.version),
            subtype_xmlid="mail.mt_note",
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "product.homologation.quote",
            "view_mode": "form",
            "res_id": new_quote.id,
        }

    def action_view_versions(self):
        self.ensure_one()
        root = self.root_id or self
        return {
            "type": "ir.actions.act_window",
            "name": _("Versiones de la precotización"),
            "res_model": "product.homologation.quote",
            "view_mode": "list,form",
            "domain": ["|", ("id", "=", root.id), ("root_id", "=", root.id)],
            "context": {"create": False},
        }
