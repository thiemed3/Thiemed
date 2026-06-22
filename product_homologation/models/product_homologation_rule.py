from odoo import fields, models, api
from odoo.exceptions import ValidationError


class ProductHomologationRule(models.Model):
    _name = "product.homologation.rule"
    _description = "Regla de sugerencia de homologación"
    _order = "priority, name"

    name = fields.Char(string="Nombre", required=True)
    rule_type = fields.Selection(
        [
            ("lowest_price", "Menor precio de venta"),
            ("lowest_cost", "Menor costo"),
            ("preferred_competitor", "Marca/competidor preferido"),
            ("highest_precision", "Mayor precisión"),
        ],
        string="Tipo de regla",
        required=True,
    )
    preferred_competitor_id = fields.Many2one(
        "res.partner",
        string="Competidor preferido",
        domain=[("supplier_rank", ">", 0)],
        help="Solo aplica para reglas de tipo 'Marca/competidor preferido'.",
    )
    priority = fields.Integer(string="Prioridad", default=10, help="Menor número = mayor prioridad")
    active = fields.Boolean(string="Activo", default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        (
            "check_preferred_competitor_required",
            "CHECK(rule_type != 'preferred_competitor' OR preferred_competitor_id IS NOT NULL)",
            "Debe seleccionar un competidor para las reglas de tipo 'Marca/competidor preferido'.",
        ),
    ]
