# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    as_fecha_invenatario = fields.Date('Inicio Movimiento de Inventario', help='Esta fecha permite dar inicio al Kardex de Productos, para Inventario Inicial', default=0)
    
    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res['as_fecha_invenatario'] = (self.env['ir.config_parameter'].sudo().get_param('res_config_settings.as_fecha_invenatario'))
        
        return res

    @api.model
    def set_values(self):
        self.env['ir.config_parameter'].sudo().set_param('res_config_settings.as_fecha_invenatario', self.as_fecha_invenatario)
        super(ResConfigSettings, self).set_values()