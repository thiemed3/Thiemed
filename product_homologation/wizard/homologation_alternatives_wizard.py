from odoo import api, fields, models, _


class ProductHomologationAlternativesWizard(models.TransientModel):
    _name = "product.homologation.alternatives.wizard"
    _description = "Asistente de selección de alternativas de homologación"

    quote_line_id = fields.Many2one(
        "product.homologation.quote.line",
        string="Línea de precotización",
        required=True,
        ondelete="cascade",
    )
    quote_id = fields.Many2one(
        related="quote_line_id.quote_id",
        string="Precotización",
    )
    customer_code = fields.Char(
        related="quote_line_id.customer_code",
        string="Código del cliente",
    )
    customer_description = fields.Text(
        related="quote_line_id.customer_description",
        string="Descripción del cliente",
    )
    candidate_ids = fields.One2many(
        "product.homologation.alternative.candidate",
        "wizard_id",
        string="Alternativas",
    )
    recommended_id = fields.Many2one(
        "product.homologation",
        string="Recomendada",
        compute="_compute_recommended",
    )
    recommendation_reason = fields.Char(
        string="Motivo de la recomendación",
        compute="_compute_recommended",
    )

    @api.depends("quote_line_id")
    def _compute_recommended(self):
        for wizard in self:
            line = wizard.quote_line_id
            recommended, reason, _ordered = line._get_possible_homologations()._recommend()
            wizard.recommended_id = recommended
            wizard.recommendation_reason = reason

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wizard in wizards:
            wizard._build_candidates()
        return wizards

    def _build_candidates(self):
        self.ensure_one()
        line = self.quote_line_id
        recommended, _reason, ordered = line._get_possible_homologations()._recommend()
        commands = []
        for homologation in ordered:
            commands.append((0, 0, {
                "wizard_id": self.id,
                "homologation_id": homologation.id,
                "recommended": homologation == recommended,
                "is_selected": homologation == line.homologation_id,
            }))
        self.candidate_ids = [(5, 0, 0)] + commands

    def _apply_selection(self, homologation):
        self.ensure_one()
        self.quote_line_id._apply_selected_homologation(homologation)
        return self.quote_id.action_open_quote()

    def action_apply_recommended(self):
        self.ensure_one()
        if not self.recommended_id:
            return {"type": "ir.actions.act_window_close"}
        return self._apply_selection(self.recommended_id)

    def action_close(self):
        return {"type": "ir.actions.act_window_close"}


class ProductHomologationAlternativeCandidate(models.TransientModel):
    _name = "product.homologation.alternative.candidate"
    _description = "Alternativa de homologación"
    _order = "recommended desc, precision_pct desc, price, id"

    wizard_id = fields.Many2one(
        "product.homologation.alternatives.wizard",
        string="Asistente",
        required=True,
        ondelete="cascade",
    )
    homologation_id = fields.Many2one(
        "product.homologation",
        string="Homologación",
        required=True,
        ondelete="cascade",
    )
    reference = fields.Char(
        related="homologation_id.customer_code",
        string="Referencia del cliente",
    )
    description = fields.Text(
        related="homologation_id.customer_description",
        string="Descripción",
    )
    brand_id = fields.Many2one(
        related="homologation_id.competitor_id",
        string="Marca/competidor",
    )
    product_id = fields.Many2one(
        related="homologation_id.product_id",
        string="Producto interno",
    )
    product_code = fields.Char(
        related="homologation_id.product_default_code",
        string="Código interno",
    )
    price = fields.Float(
        related="homologation_id.product_price",
        string="Precio",
    )
    precision_pct = fields.Float(
        related="homologation_id.precision_pct",
        string="Precisión (%)",
    )
    homologation_level = fields.Selection(
        related="homologation_id.homologation_level",
        string="Nivel",
    )
    observation = fields.Text(
        related="homologation_id.observation",
        string="Observación",
    )
    state = fields.Selection(
        related="homologation_id.state",
        string="Estado",
    )
    recommended = fields.Boolean(string="Recomendada", readonly=True)
    is_selected = fields.Boolean(string="Seleccionada", readonly=True)

    def action_select(self):
        self.ensure_one()
        return self.wizard_id._apply_selection(self.homologation_id)
