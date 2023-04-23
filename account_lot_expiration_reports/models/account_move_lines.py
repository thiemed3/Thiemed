from odoo import fields, models, api
import json

class AccountMoveLines(models.Model):
    _inherit = 'account.move.line'

    cantidad_lote = fields.Char(string='Cantidad Lote', compute='_compute_cantidad_lote')

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
        # si el diccionario esta vacio actualizar con el valor de la cantidad de la linea de factura

        for key, value in cantidad_lote.items():
            if key == 'SIN LOTE':
                cantidad_lote[key] = {'cantidad': value, 'nombre': key, 'fecha_vencimiento': ''}
            else:
                fecha_vencimiento = self.env['stock.production.lot'].search([('name', '=', key)]).expiration_date
                if len(fecha_vencimiento) > 1:
                    cantidad_lote[key] = {'cantidad': value, 'nombre': key, 'fecha_vencimiento': fecha_vencimiento.strftime('%d/%m/%Y')}
                else:
                    cantidad_lote[key] = {'cantidad': value, 'nombre': key, 'fecha_vencimiento': ''}


        return cantidad_lote

    def get_lote_cantidad(self, diccionario, llave):
        return diccionario.get(llave).get('cantidad')

    def get_lote_fvencimiento(self, diccionario, llave):
        return diccionario.get(llave).get('fecha_vencimiento')

