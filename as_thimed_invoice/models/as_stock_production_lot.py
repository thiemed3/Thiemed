# -*- coding: utf-8 -*-
from odoo import api, fields, models

class as_helpdesk_notify(models.Model):
    _inherit = 'stock.lot'

    as_cantidad = fields.Char(string='Cantidad lote', compute='_get_cantidad_lote', store=True)

    @api.depends('product_qty')
    def _get_cantidad_lote(self):
        for lot in self:
            lot.as_cantidad = lot.product_qty

    def get_cantidad_lote(self):
        self._get_cantidad_lote()
