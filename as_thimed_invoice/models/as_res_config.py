# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    _AS_FECHA_INVENTARIO_PARAM = 'res_config_settings.as_fecha_invenatario'

    as_fecha_invenatario = fields.Date(
        'Inicio Movimiento de Inventario',
        help='Esta fecha permite dar inicio al Kardex de Productos, para Inventario Inicial',
    )

    def get_values(self):
        res = super().get_values()
        value = self.env['ir.config_parameter'].sudo().get_param(self._AS_FECHA_INVENTARIO_PARAM)
        res.update(as_fecha_invenatario=fields.Date.to_date(value) if value else False)
        return res

    def set_values(self):
        super().set_values()
        value = fields.Date.to_string(self.as_fecha_invenatario) if self.as_fecha_invenatario else ''
        self.env['ir.config_parameter'].sudo().set_param(self._AS_FECHA_INVENTARIO_PARAM, value)
