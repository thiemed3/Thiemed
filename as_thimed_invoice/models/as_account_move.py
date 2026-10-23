# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SO(models.Model):
    _inherit = 'account.move'

    as_reference= fields.Char('Referencia/Descripción')

    @api.onchange('l10n_cl_reference_ids')
    @api.depends('l10n_cl_reference_ids')
    def gte_refrencia(self):
        if self.l10n_cl_reference_ids:
            self.as_reference = self.l10n_cl_reference_ids[0].origin_doc_number
            self.ref = self.l10n_cl_reference_ids[0].origin_doc_number
