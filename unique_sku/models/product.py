# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import ValidationError

class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _check_unique_default_code(self):
        for template in self.filtered('default_code'):
            duplicate = self.search([
                ('id', '!=', template.id),
                ('default_code', '=', template.default_code),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    "Un código de referencia interna, sólo puede ser asignado a un producto: %s",
                    template.default_code,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        templates = super().create(vals_list)
        templates._check_unique_default_code()
        return templates

    def write(self, vals):
        result = super().write(vals)
        if 'default_code' in vals:
            self._check_unique_default_code()
        return result
