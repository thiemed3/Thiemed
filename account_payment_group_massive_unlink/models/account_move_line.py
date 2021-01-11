# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools.translate import _

class AccountPaymentGroup(models.Model):
    _inherit = "account.payment.group"
    
    # # @api.one
    @api.model
    def unlink_selected(self):
        list_ids = []
        for record_m_l in self.debt_move_line_ids:
            if record_m_l.to_unlink:
                list_ids.append(record_m_l.id)
                record_m_l.write({'to_unlink': False})
        
        for i in list_ids:
            self.write({'debt_move_line_ids': [(3, i)]})

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # inverse field of the one created on payment groups, used by other modules
    # like sipreco
    to_unlink = fields.Boolean('A borrar')
