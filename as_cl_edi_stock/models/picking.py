# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = "stock.picking"
    
    as_ref_gde = fields.Char(string='Referencia GDE')

    @api.onchange('l10n_latam_document_number','l10n_latam_document_type_id','l10n_cl_dte_status')
    @api.depends('l10n_latam_document_number','l10n_latam_document_type_id','l10n_cl_dte_status')
    def as_get_ref_guia_despacho(self):
        for pick in self:
            if pick.l10n_latam_document_number:
                pick.as_ref_gde = str(pick.l10n_latam_document_type_id.report_name)+' '+str(pick.l10n_latam_document_number)
            else:
                pick.as_ref_gde = 'N/A'

    def create_delivery_guide(self):
        res = super(StockPicking, self).create_delivery_guide()
        self.as_get_ref_guia_despacho()
        return res
