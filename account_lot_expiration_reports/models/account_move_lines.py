from odoo import fields, models, api
import json

class AccountMoveLines(models.Model):
    _inherit = 'account.move.line'

    # cantidad_lote = fields.Char(string='Cantidad Lote', compute='_compute_cantidad_lote')
    cantidad_lote = fields.Char(string='Cantidad Lote')
    # stock_move_line_id = fields.One2many('stock.move.line', 'account_move_line_id', string='Linea de Movimiento')


    def _compute_cantidad_lote(self):
        for rec in self:
            cantidad_lote = {}

            # RECORRER LOS MOVIENMIENTOS DE LA LINEA DE PEDIDO DE VENTA Y OBTENER EL VALOR DEL CAMPO cantidad_lote.
            for sale_line in rec.sale_line_ids:
                if sale_line.cantidad_lote:
                    cantidad_lote.update(json.loads(sale_line.cantidad_lote))

            if not cantidad_lote:
                    cantidad_lote = {'SIN LOTE': sale_line.qty_invoiced}

            rec.cantidad_lote = json.dumps(cantidad_lote)

    def get_lote_lines(self):
        cantidad_lote = json.loads(self.cantidad_lote)
        # si el diccionario esta vacio actualizar con el valor de la cantidad de la linea de facturaz


        for key, value in cantidad_lote.items():

            for rec in self:
                move_lines = rec.sale_line_ids.move_ids.mapped('move_line_ids').filtered(lambda x: x.product_id == rec.product_id)
                sale_lines = rec.mapped('sale_line_ids').filtered(lambda x: x.product_id == rec.product_id)
                if sale_lines.product_uom.uom_type == 'reference':
                    if key == 'SIN LOTE':
                        cantidad_lote[key] = {'cantidad': value,
                                              'nombre': key,
                                              'fecha_vencimiento': '',
                                              'udm': move_lines.product_uom_id.name,
                                              'precio': sale_lines.price_unit,
                                              'ratio': 1}
                    else:
                        fecha_vencimiento = self.env[stock.lot'].search([('name', '=', key),('product_id', '=', self.product_id.id)]).expiration_date
                        # fecha = fecha_vencimiento.expiration_date
                        if fecha_vencimiento:
                            cantidad_lote[key] = {'cantidad': value,
                                                  'nombre': key,
                                                  'fecha_vencimiento': fecha_vencimiento.strftime('%d/%m/%Y'),
                                                  'udm': move_lines.product_uom_id.name,
                                                  'precio': sale_lines.price_unit,
                                                  'ratio': 1}
                        else:
                            cantidad_lote[key] = {'cantidad': value,
                                                  'nombre': key,
                                                  'fecha_vencimiento': '',
                                                  'udm': move_lines.product_uom_id.name,
                                                  'precio': sale_lines.price_unit,
                                                  'ratio': 1}
                if sale_lines.product_uom.uom_type == 'bigger':

                    if key == 'SIN LOTE':
                        valor = rec.quantity * sale_lines.product_uom.factor_inv
                        cantidad_lote[key] = {'cantidad': value,
                                              'nombre': key,
                                              'fecha_vencimiento': '',
                                              'udm': move_lines.product_uom_id.name,
                                              'precio': sale_lines.price_unit,
                                              'ratio': int(sale_lines.product_uom.factor_inv)}
                    else:
                        fecha_vencimiento = self.env['stock.lot'].search([('name', '=', key),('product_id', '=', self.product_id.id)]).expiration_date
                        # fecha = fecha_vencimiento.expiration_date
                        if fecha_vencimiento:
                            cantidad_lote[key] = {'cantidad': value,
                                                  'nombre': key,
                                                  'fecha_vencimiento': fecha_vencimiento.strftime('%d/%m/%Y'),
                                                  'udm': move_lines.product_uom_id.name,
                                                  'precio': sale_lines.price_unit,
                                                  'ratio': int(sale_lines.product_uom.factor_inv)}
                        else:
                            cantidad_lote[key] = {'cantidad': value,
                                                  'nombre': key,
                                                  'fecha_vencimiento': '',
                                                  'udm': move_lines.product_uom_id.name,
                                                  'precio': sale_lines.price_unit,
                                                  'ratio': int(sale_lines.product_uom.factor_inv)}


        return cantidad_lote

    def get_lote_cantidad(self, diccionario, llave):
        return diccionario.get(llave).get('cantidad')

    def get_lote_fvencimiento(self, diccionario, llave):
        return diccionario.get(llave).get('fecha_vencimiento')


