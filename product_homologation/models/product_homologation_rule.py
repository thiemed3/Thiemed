from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

RULE_TYPES = [
    ("highest_precision", "Mayor precisión"),
    ("lowest_price", "Menor precio de venta"),
    ("lowest_cost", "Menor costo"),
    ("preferred_competitor", "Marca/competidor preferido"),
]


class ProductHomologationRule(models.Model):
    _name = "product.homologation.rule"
    _description = "Regla de sugerencia de homologación"
    _order = "priority, name"

    name = fields.Char(string="Nombre", required=True)
    rule_type = fields.Selection(
        RULE_TYPES,
        string="Tipo de regla",
        required=True,
        default="highest_precision",
    )
    preferred_competitor_id = fields.Many2one(
        "res.partner",
        string="Competidor preferido",
        domain=[("supplier_rank", ">", 0)],
        help="Solo aplica para reglas de tipo 'Marca/competidor preferido'.",
    )
    priority = fields.Integer(
        string="Prioridad",
        default=10,
        help="Menor número = mayor prioridad. Las reglas con mayor prioridad "
             "se aplican al final y dominan el resultado; las de menor prioridad "
             "actúan como desempate.",
    )
    active = fields.Boolean(string="Activo", default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
    )

    _preferred_competitor_required = models.Constraint(
        "CHECK(rule_type != 'preferred_competitor' OR preferred_competitor_id IS NOT NULL)",
        "Debe seleccionar un competidor para las reglas de tipo 'Marca/competidor preferido'.",
    )

    @api.constrains("priority")
    def _check_priority(self):
        for rule in self:
            if rule.priority < 0:
                raise ValidationError(_("La prioridad debe ser un número positivo."))

    @api.onchange("rule_type")
    def _onchange_rule_type(self):
        if self.rule_type != "preferred_competitor":
            self.preferred_competitor_id = False

    def _sort_key(self, homologation):
        """Clave de orden ascendente: el primer registro es el mejor.

        Se usa junto con un ordenamiento estable encadenado en
        ``product.homologation._sort_for_rules``.
        """
        self.ensure_one()
        # La clave no incluye el id del registro para que ``sorted`` (estable)
        # conserve el orden alcanzado por las reglas de menor prioridad y así
        # estas puedan actuar como desempate.
        if self.rule_type == "highest_precision":
            return (-(homologation.precision_pct or 0.0),)
        if self.rule_type == "lowest_price":
            return (homologation.product_price or 0.0,)
        if self.rule_type == "lowest_cost":
            return (homologation.product_standard_price or 0.0,)
        if self.rule_type == "preferred_competitor":
            preferred = self.preferred_competitor_id
            is_preferred = bool(preferred and homologation.competitor_id == preferred)
            return (0 if is_preferred else 1,)
        return (0,)

    def _get_reason(self):
        self.ensure_one()
        labels = dict(RULE_TYPES)
        return labels.get(self.rule_type, self.name)
