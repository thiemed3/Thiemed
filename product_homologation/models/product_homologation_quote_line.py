from odoo import fields, models, api


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
    customer_description = fields.Text(
        string="Descripción del cliente",
        help="Descripción original del producto.",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto interno",
        domain=[("active", "=", True)],
        help="Producto de Thiemed sugerido como homólogo.",
    )
    homologation_id = fields.Many2one(
        "product.homologation",
        string="Homologación aplicada",
        help="Registro de homologación que vinculó este código al producto interno.",
    )
    state = fields.Selection(
        [("pending", "Pendiente"), ("matched", "Homologado"), ("unmatched", "Sin match")],
        string="Estado",
        default="pending",
        required=True,
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

    @api.onchange("customer_code")
    def _onchange_customer_code(self):
        if not self.customer_code:
            return
        Homologation = self.env["product.homologation"]
        domain = [("customer_code", "=", self.customer_code)]
        match = Homologation.search(domain, limit=1)
        if match and match.product_id:
            self.customer_description = match.customer_description
            self.product_id = match.product_id
            self.homologation_id = match
            self.state = "matched"

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id and self.state != "matched":
            self.state = "matched"
        elif not self.product_id:
            self.state = "pending"

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._ensure_homologation()
        return lines

    def write(self, vals):
        result = super().write(vals)
        if "customer_code" in vals or "product_id" in vals:
            self._ensure_homologation()
        return result

    def _ensure_homologation(self):
        for line in self:
            if not line.customer_code or not line.product_id:
                continue
            Homologation = self.env["product.homologation"]
            existing = Homologation.search([
                ("customer_code", "=", line.customer_code),
                ("product_id", "=", line.product_id.id),
            ], limit=1)
            if existing:
                if line.homologation_id != existing:
                    line.homologation_id = existing
                continue
            competitor = line.product_id.seller_ids[:1].partner_id
            if not competitor:
                continue
            hom = Homologation.create({
                "competitor_id": competitor.id,
                "customer_code": line.customer_code,
                "customer_description": line.customer_description or line.product_id.name,
                "product_id": line.product_id.id,
                "state": "draft",
            })
            line.homologation_id = hom
