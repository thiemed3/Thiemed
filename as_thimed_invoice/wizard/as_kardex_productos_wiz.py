# -*- coding: utf-8 -*-

from datetime import datetime
from odoo import api, fields, models

class as_kardex_productos_wiz(models.TransientModel):
    _name="as.kardex.productos.wiz"
    _description = "Warehouse Reports by AhoraSoft"
    
    #numeracion para ventas
    def _get_default_fecha_inicial(self):
        fecha = ''
        fecha = self.env['ir.config_parameter'].sudo().get_param('res_config_settings.as_fecha_invenatario')
        return fecha

    start_date = fields.Date('Desde la Fecha', default=fields.Date.context_today)
    end_date = fields.Date('Hasta la Fecha', default=fields.Date.context_today)
    as_almacen = fields.Many2many('stock.location', string="Almacen", domain="[('usage', '=', 'internal')]")
    as_productos = fields.Many2many('product.product', string="Productos")
    category_ids = fields.Many2many('product.category', string="Categoria de Productos")
    as_consolidado = fields.Boolean(string="Consolidado", default=False)
    as_categ_levels = fields.Integer(string="Niveles de categorias", help=u"Debe ser un entero igual o mayor a 1", default=2)
    as_fecha_inicial = fields.Date('Inicio Movimiento de Inventario', default=_get_default_fecha_inicial)

    def export_xls(self):
        context = self._context
        datas = {'ids': context.get('active_ids', [])}
        datas['model'] = 'as.kardex.productos.wiz'
        datas['form'] = self.read()[0]
        for field in datas['form'].keys():
            if isinstance(datas['form'][field], tuple):
                datas['form'][field] = datas['form'][field][0]
        if context.get('xls_export'):
            return self.env.ref('as_thimed_invoice.kardex_productos_xlsx').report_action(self, data=datas)