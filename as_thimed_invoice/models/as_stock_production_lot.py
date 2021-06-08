# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.tools.safe_eval import safe_eval
from datetime import datetime, timedelta

class as_helpdesk_notify(models.Model):
    _inherit = 'stock.production.lot'

    as_cantidad = fields.Char(string='Cantidad lote',compute='_get_cantidad_lote',store=True)

    @api.depends('product_qty')
    def _get_cantidad_lote(self):
        for lot in self:
            lot.as_cantidad =lot.product_qty
