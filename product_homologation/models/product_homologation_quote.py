from odoo import fields, models, api, _
from odoo.exceptions import UserError


class ProductHomologationQuote(models.Model):
    _name = "product.homologation.quote"
    _description = "Precotización de homologación"
    _order = "id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"

    name = fields.Char(string="Referencia", required=True, index=True, default="Nuevo")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "name" not in vals or vals.get("name") == "Nuevo":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("product.homologation.quote")
                    or "Nuevo"
                )
        return super().create(vals_list)
    lead_id = fields.Many2one("crm.lead", string="Oportunidad CRM", tracking=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        required=True,
        domain=[("active", "=", True)],
        tracking=True
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
        tracking=True
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Presupuesto generado",
        readonly=True,
        tracking=True
    )
    line_count = fields.Integer(
        string="Líneas",
        compute="_compute_line_count",
    )
    matched_count = fields.Integer(
        string="Homologadas",
        compute="_compute_line_count",
    )
    notes = fields.Text(string="Notas")
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
    )

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

    def action_open_quote(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "product.homologation.quote",
            "view_mode": "form",
            "res_id": self.id,
        }

    def _get_incomplete_lines(self):
        return self.line_ids.filtered(
            lambda line: not (
                line.state == "matched"
                and line.product_id
                and line.homologation_id
                and line.homologation_id.state == "validated"
            )
        )

    def _check_lines_ready_for_sale(self):
        for quote in self:
            incomplete_lines = quote._get_incomplete_lines()
            if incomplete_lines:
                raise UserError(_(
                    "No se puede continuar: quedan %s línea(s) pendientes de homologar. "
                    "Todas las líneas deben tener producto y homologación validada."
                ) % len(incomplete_lines))

    def action_confirm_homologation(self):
        self._check_lines_ready_for_sale()
        self.state = "homologated"

    def action_cancel(self):
        self.state = "cancelled"

    def action_draft(self):
        self.state = "draft"

    def action_convert_to_sale(self):
        self.ensure_one()
        if self.state == "converted" or self.sale_order_id:
            raise UserError(_(
                "Esta precotización ya fue convertida a presupuesto. "
                "No se puede crear un segundo presupuesto."
            ))
        self._check_lines_ready_for_sale()
        SaleOrder = self.env["sale.order"]
        order = SaleOrder.create({
            "partner_id": self.partner_id.id,
            "opportunity_id": self.lead_id.id,
            "origin": self.name,
        })
        for line in self.line_ids:
            code = line.customer_code or _("Sin código")
            homologation_code = line.homologation_id.customer_code or _("Sin código")
            self.env["sale.order.line"].create({
                "order_id": order.id,
                "product_id": line.product_id.id,
                "product_uom_qty": line.quantity,
                "price_unit": line.price_unit,
                "name": self._prepare_sale_line_name(line, code, homologation_code),
                "homologation_customer_code": line.customer_code,
                "homologation_customer_description": line.customer_description,
                "homologation_observation": line.homologation_id.observation,
                "homologation_quote_observation": line.observation,
                "homologation_level": line.homologation_id.homologation_level,
                "homologation_precision_pct": line.homologation_id.precision_pct,
                "homologation_quote_line_id": line.id,
            })
        self.sale_order_id = order.id
        self.state = "converted"
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
