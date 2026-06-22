from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    competitor = fields.Boolean(
        string="Es competidor/marca",
        help="Marcar si este contacto representa un competidor o marca "
             "(ej. Xilong, Johnson, etc.) cuyos productos se homologan.",
    )
