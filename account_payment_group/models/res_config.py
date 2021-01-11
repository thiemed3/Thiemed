# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools.translate import _


class AccountConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    #double_validation = fields.Boolean(related='company_id.double_validation')
    double_validation = fields.Boolean('Apply Double Validation', related='company_id.double_validation')



