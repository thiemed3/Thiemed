from odoo import fields, models, api


class ProductHomologationQuote(models.Model):
    _name = "product.homologation.quote"
    _description = "Precotización de homologación"
    _order = "id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"

    name = fields.Char(string="Referencia", required=True, index=True, default="Nuevo")

    @api.model
    def create(self, vals):
        if "name" not in vals or vals.get("name") == "Nuevo":
            vals["name"] = (
                self.env["ir.sequence"].next_by_code("product.homologation.quote")
                or "Nuevo"
            )
        return super().create(vals)
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

    def _compute_line_count(self):
        for q in self:
            lines = q.line_ids
            q.line_count = len(lines)
            q.matched_count = len(lines.filtered(lambda l: l.state == "matched"))

    def action_open_quote(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "product.homologation.quote",
            "view_mode": "form",
            "res_id": self.id,
        }

    def action_confirm_homologation(self):
        self.state = "homologated"

    def action_cancel(self):
        self.state = "cancelled"

    def action_draft(self):
        self.state = "draft"

    def action_convert_to_sale(self):
        self.ensure_one()
        SaleOrder = self.env["sale.order"]
        order = SaleOrder.create({
            "partner_id": self.partner_id.id,
            "opportunity_id": self.lead_id.id,
            "origin": self.name,
        })
        for line in self.line_ids.filtered(lambda l: l.product_id and l.state == "matched"):
            self.env["sale.order.line"].create({
                "order_id": order.id,
                "product_id": line.product_id.id,
                "product_uom_qty": line.quantity,
                "price_unit": line.price_unit,
                "name": (
                    f"[{line.customer_code}] {line.customer_description}\n"
                    f"Homologación: {line.homologation_id.customer_code} → {line.product_id.display_name}"
                ),
                "homologation_customer_code": line.customer_code,
                "homologation_customer_description": line.customer_description,
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
