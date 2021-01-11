# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.tools.safe_eval import safe_eval
from datetime import datetime, timedelta

class stockpicking(models.Model):
    _inherit = 'stock.picking'

    # @api.multi
    def _get_reference(self):
        for pick in self:
            reference =''
            for move in pick.move_lines:
                reference = move.reference
            pick.referencia = reference
            pick.date_done_doc = pick.date_done

    referencia = fields.Char(string='Referencia Tranferencia',compute='_get_reference')
    date_done_doc = fields.Datetime('Fecha documento', copy=False, compute='_get_reference', help="Completion Date of Transfer")