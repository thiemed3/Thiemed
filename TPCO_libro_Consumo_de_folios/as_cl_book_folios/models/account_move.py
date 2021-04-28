import decimal
import logging
from datetime import date, datetime, timedelta
import pytz
from six import string_types

from odoo import api, fields, models, tools
from odoo.exceptions import UserError
from odoo.tools.translate import _
from odoo.addons import decimal_precision as dp
_logger = logging.getLogger(__name__)


try:
    from facturacion_electronica import facturacion_electronica as fe
    from facturacion_electronica import clase_util as util
except Exception as e:
    _logger.warning("Problema al cargar Facturación electrónica: %s" % str(e))
try:
    from io import BytesIO
except ImportError:
    _logger.warning("no se ha cargado io")
try:
    import pdf417gen
except ImportError:
    _logger.warning("Cannot import pdf417gen library")
try:
    import base64
except ImportError:
    _logger.warning("Cannot import base64 library")
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    _logger.warning("no se ha cargado PIL")


TYPE2JOURNAL = {
    "out_invoice": "sale",
    "in_invoice": "purchase",
    "out_refund": "sale",
    "in_refund": "purchase",
}


class AccountMove(models.Model):
    _inherit = "account.move"

    iva_uso_comun = fields.Boolean(string="Iva Uso Común", readonly=True, states={"draft": [("readonly", False)]},)
    no_rec_code = fields.Selection(
        [
            ("1", "Compras destinadas a IVA a generar operaciones no gravados o exentas."),
            ("2", "Facturas de proveedores registrados fuera de plazo."),
            ("3", "Gastos rechazados."),
            ("4", "Entregas gratuitas (premios, bonificaciones, etc.) recibidos."),
            ("9", "Otros."),
        ],
        string="Código No recuperable",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )  # @TODO select 1 automático si es emisor 2Categoría
    ticket = fields.Boolean(
        string="Formato Ticket", default=False, readonly=True, states={"draft": [("readonly", False)]},
    )
    ind_servicio = fields.Selection(
        [
            ('1', "1.- Factura de servicios periódicos domiciliarios 2"),
            ('2', "2.- Factura de otros servicios periódicos"),
            (
                '3',
                "3.- Factura de Servicios. (en caso de Factura de Exportación: Servicios calificados como tal por Aduana)",
            ),
            ('4', "4.- Servicios de Hotelería"),
            ('5', "5.- Servicio de Transporte Terrestre Internacional"),
        ]
    )
    sii_xml_request = fields.Many2one("sii.xml.envio", string="SII XML Request", copy=False)
    def _get_move_imps(self):
        imps = {}
        for l in self.line_ids:
            if l.tax_line_id:
                if l.tax_line_id:
                    if l.tax_line_id.id not in imps:
                        imps[l.tax_line_id.id] = {
                            "tax_id": l.tax_line_id.id,
                            "credit": 0,
                            "debit": 0,
                            "code": l.tax_line_id.l10n_cl_sii_code,
                        }
                    imps[l.tax_line_id.id]["credit"] += l.credit
                    imps[l.tax_line_id.id]["debit"] += l.debit
            elif l.tax_ids and l.tax_ids[0].amount == 0:  # caso monto exento
                if not l.tax_ids[0].id in imps:
                    imps[l.tax_ids[0].id] = {
                        "tax_id": l.tax_ids[0].id,
                        "credit": 0,
                        "debit": 0,
                        "code": l.tax_ids[0].l10n_cl_sii_code,
                    }
                imps[l.tax_ids[0].id]["credit"] += l.credit
                imps[l.tax_ids[0].id]["debit"] += l.debit
        return imps

    def totales_por_movimiento(self):
        move_imps = self._get_move_imps()
        imps = {
            "iva": 0,
            "exento": 0,
            "otros_imps": 0,
        }
        for _key, i in move_imps.items():
            if i["code"] in [14]:
                imps["iva"] += i["credit"] or i["debit"]
            elif i["code"] == 0:
                imps["exento"] += i["credit"] or i["debit"]
            else:
                imps["otros_imps"] += i["credit"] or i["debit"]
        imps["neto"] = self.amount_total - imps["otros_imps"] - imps["exento"] - imps["iva"]
        return imps

    def currency_base(self):
        return self.env.ref("base.CLP")

    def currency_target(self):
        if self.currency_id != self.currency_base():
            return self.currency_id
        return False

    def format_vat(self, value):
        ''' Se Elimina el 0 para prevenir problemas con el sii, ya que las muestras no las toma si va con
        el 0 , y tambien internamente se generan problemas'''
        if not value or value=='' or value == 0:
            value ="CL666666666"
            #@TODO opción de crear código de cliente en vez de rut genérico
        rut = value[:10] + '-' + value[10:]
        rut = rut.replace('CL0','').replace('CL','')
        return rut


    def _nc_boleta(self):
        if not self.referencias or self.move_type != "out_refund":
            return False
        for r in self.referencias:
            pass
            # return r.l10n_cl_reference_doc_type_selection.es_nc_boleta()
        return False

    def get_folio(self):
        # saca el folio directamente de la secuencia
        if self.l10n_latam_document_number:
            if 'FAC' not in self.l10n_latam_document_number:
                if 'BEL' not in self.l10n_latam_document_number:
                    return int(self.l10n_latam_document_number)
                else:
                    return int(self.l10n_latam_document_number.split('BEL')[1])
            else:
                return int(self.l10n_latam_document_number.split('FAC')[1])
        else:
            return int(self.l10n_latam_document_number)


    def _id_doc(self, taxInclude=False, MntExe=0):
        IdDoc = {}
        IdDoc["TipoDTE"] = self.l10n_latam_document_type_id.code
        IdDoc["Folio"] = self.get_folio()
        IdDoc["FchEmis"] = self.invoice_date.strftime("%Y-%m-%d")
        if self._es_boleta():
            IdDoc["IndServicio"] = 3  # @TODO agregar las otras opciones a la fichade producto servicio
        if self.ticket and not self._es_boleta():
            IdDoc["TpoImpresion"] = "T"
        if self.ind_servicio:
            IdDoc["IndServicio"] = self.ind_servicio
        # todo: forma de pago y fecha de vencimiento - opcional
        if taxInclude and MntExe == 0 and not self._es_boleta():
            IdDoc["MntBruto"] = 1
        if not self._es_boleta():
            IdDoc["FmaPago"] = 1
        if not taxInclude and self._es_boleta():
            IdDoc["IndMntNeto"] = 2
        # if self._es_boleta():
        # Servicios periódicos
        #    IdDoc['PeriodoDesde'] =
        #    IdDoc['PeriodoHasta'] =
        if not self._es_boleta() and self.invoice_date_due:
            IdDoc["FchVenc"] = self.invoice_date_due.strftime("%Y-%m-%d") or datetime.strftime(datetime.now(), "%Y-%m-%d")
        return IdDoc

    def _emisor(self):
        Emisor = {}
        Emisor["RUTEmisor"] = self.company_id.partner_id.vat
        if self._es_boleta():
            Emisor["RznSocEmisor"] = self._acortar_str(self.company_id.partner_id.name, 100)
            Emisor["GiroEmisor"] = self._acortar_str(self.company_id.l10n_cl_activity_description, 80)
        else:
            Emisor["RznSoc"] = self._acortar_str(self.company_id.partner_id.name, 100)
            Emisor["GiroEmis"] = self._acortar_str(self.company_id.l10n_cl_activity_description, 80)
            if self.company_id.phone:
                Emisor["Telefono"] = self._acortar_str(self.company_id.phone, 20)
            Emisor["CorreoEmisor"] = self.company_id.l10n_cl_dte_email
            Emisor["Actecos"] = self._actecos_emisor()
        dir_origen = self.company_id
        if self.journal_id.sucursal_id:
            Emisor['Sucursal'] = self._acortar_str(self.journal_id.sucursal_id.partner_id.name, 20)
            Emisor["CdgSIISucur"] = self._acortar_str(self.journal_id.sucursal_id.l10n_cl_sii_code, 9)
            dir_origen = self.journal_id.sucursal_id.partner_id
        Emisor['DirOrigen'] = self._acortar_str(dir_origen.street + ' ' + (dir_origen.street2 or ''), 70)
        if not dir_origen.state_id:
            raise UserError("Debe ingresar la Comuna de compañía emisora")
        Emisor['CmnaOrigen'] = dir_origen.state_id.name
        if not dir_origen.city:
            raise UserError("Debe ingresar la Ciudad de compañía emisora")
        Emisor["CiudadOrigen"] = self.company_id.city
        Emisor["Modo"] = "produccion" if self.company_id.l10n_cl_dte_service_provider == "SII" else "certificacion"
        Emisor["NroResol"] = self.company_id.l10n_cl_dte_resolution_number
        Emisor["FchResol"] = self.company_id.l10n_cl_dte_resolution_date.strftime("%Y-%m-%d")
        Emisor["ValorIva"] = 19
        return Emisor

    def _actecos_emisor(self):
        actecos = []
        if not self.company_id.l10n_cl_company_activity_ids:
            raise UserError("El Diario no tiene ACTECOS asignados")
        for acteco in self.company_id.l10n_cl_company_activity_ids:
            actecos.append(acteco.code)
        return actecos

    def _receptor(self):
        Receptor = {}
        commercial_partner_id = self.commercial_partner_id or self.partner_id.commercial_partner_id
        if not commercial_partner_id.vat and not self._es_boleta() and not self._nc_boleta():
            raise UserError("Debe Ingresar RUT Receptor")
        # if self._es_boleta():
        #    Receptor['CdgIntRecep']
        Receptor["RUTRecep"] = commercial_partner_id.vat
        Receptor["RznSocRecep"] = self._acortar_str(commercial_partner_id.name, 100)
        if not self.partner_id or Receptor["RUTRecep"] == "66666666-6":
            return Receptor
        if not self._es_boleta() and not self._nc_boleta() and self.move_type not in ["in_invoice", "in_refund"]:
            GiroRecep =commercial_partner_id.l10n_cl_activity_description
            if not GiroRecep:
                raise UserError(_("Seleccione giro del partner"))
            Receptor["GiroRecep"] = self._acortar_str(GiroRecep, 40)
        if self.partner_id.phone or commercial_partner_id.phone:
            Receptor["Contacto"] = self._acortar_str(
                self.partner_id.phone or commercial_partner_id.phone or self.partner_id.email, 80
            )
        if (
            commercial_partner_id.email
            or commercial_partner_id.l10n_cl_dte_email
            or self.partner_id.email
            or self.partner_id.l10n_cl_dte_email
        ) and not self._es_boleta():
            Receptor["CorreoRecep"] = (
                commercial_partner_id.l10n_cl_dte_email
                or self.partner_id.l10n_cl_dte_email
                or commercial_partner_id.email
                or self.partner_id.email
            )
        street_recep = self.partner_id.street or commercial_partner_id.street or False
        if (
            not street_recep
            and not self._es_boleta()
            and not self._nc_boleta()
            and self.move_type not in ["in_invoice", "in_refund"]
        ):
            # or self.indicador_servicio in [1, 2]:
            raise UserError("Debe Ingresar dirección del cliente")
        street2_recep = self.partner_id.street2 or commercial_partner_id.street2 or False
        if street_recep or street2_recep:
            Receptor["DirRecep"] = self._acortar_str(street_recep + (" " + street2_recep if street2_recep else ""), 70)
        cmna_recep = self.partner_id.state_id.name or commercial_partner_id.state_id.name
        if (
            not cmna_recep
            and not self._es_boleta()
            and not self._nc_boleta()
            and self.move_type not in ["in_invoice", "in_refund"]
        ):
            raise UserError("Debe Ingresar Comuna del cliente")
        else:
            Receptor["CmnaRecep"] = cmna_recep
        ciudad_recep = self.partner_id.city or commercial_partner_id.city
        if ciudad_recep:
            Receptor["CiudadRecep"] = ciudad_recep
        return Receptor

    def _encabezado(self, MntExe=0, no_product=False, taxInclude=False):
        Encabezado = {}
        Encabezado["IdDoc"] = self._id_doc(taxInclude, MntExe)
        Encabezado["Emisor"] = self._emisor()
        Encabezado["Receptor"] = self._receptor()
        currency_base = self.currency_base()
        another_currency_id = self.currency_target()
        MntExe, MntNeto, IVA, TasaIVA, MntTotal, MntBase = self._totales(MntExe, no_product, taxInclude)
        Encabezado["Totales"] = self._totales_normal(currency_base, MntExe, MntNeto, IVA, TasaIVA, MntTotal, MntBase)
        if another_currency_id:
            Encabezado["OtraMoneda"] = self._totales_otra_moneda(
                another_currency_id, MntExe, MntNeto, IVA, TasaIVA, MntTotal, MntBase
            )
        return Encabezado
    def _totales_otra_moneda(self, currency_id, MntExe, MntNeto, IVA, TasaIVA, MntTotal=0, MntBase=0):
        Totales = {}
        Totales["TpoMoneda"] = self._acortar_str(currency_id.abreviatura, 15)
        Totales["TpoCambio"] = round(currency_id.rate, 10)
        if MntNeto > 0:
            if currency_id != self.currency_id:
                MntNeto = currency_id._convert(MntNeto, self.currency_id, self.company_id, self.invoice_date)
            Totales["MntNetoOtrMnda"] = MntNeto
        if MntExe:
            if currency_id != self.currency_id:
                MntExe = currency_id._convert(MntExe, self.currency_id, self.company_id, self.invoice_date)
            Totales["MntExeOtrMnda"] = MntExe
        if MntBase and MntBase > 0:
            Totales["MntFaeCarneOtrMnda"] = MntBase
        if TasaIVA:
            if currency_id != self.currency_id:
                IVA = currency_id._convert(IVA, self.currency_id, self.company_id, self.invoice_date)
            Totales["IVAOtrMnda"] = IVA
        if currency_id != self.currency_id:
            MntTotal = currency_id._convert(MntTotal, self.currency_id, self.company_id, self.invoice_date)
        Totales["MntTotOtrMnda"] = MntTotal
        # Totales['MontoNF']
        # Totales['TotalPeriodo']
        # Totales['SaldoAnterior']
        # Totales['VlrPagar']
        return Totales

    def _totales_normal(self, currency_id, MntExe, MntNeto, IVA, TasaIVA, MntTotal=0, MntBase=0):
        Totales = {}
        if MntNeto > 0:
            if currency_id != self.currency_id:
                MntNeto = currency_id._convert(MntNeto, self.currency_id, self.company_id, self.invoice_date)
            Totales["MntNeto"] = currency_id.round(MntNeto)
        if MntExe:
            if currency_id != self.currency_id:
                MntExe = currency_id._convert(MntExe, self.currency_id, self.company_id, self.invoice_date)
            Totales["MntExe"] = currency_id.round(MntExe)
        if MntBase > 0:
            Totales["MntBase"] = currency_id.round(MntBase)
        if TasaIVA:
            Totales["TasaIVA"] = TasaIVA
            if currency_id != self.currency_id:
                IVA = currency_id._convert(IVA, self.currency_id, self.company_id, self.invoice_date)
            Totales["IVA"] = currency_id.round(IVA)
        if currency_id != self.currency_id:
            MntTotal = currency_id._convert(MntTotal, self.currency_id, self.company_id, self.invoice_date)
        Totales["MntTotal"] = currency_id.round(MntTotal)
        # Totales['MontoNF']
        # Totales['TotalPeriodo']
        # Totales['SaldoAnterior']
        # Totales['VlrPagar']
        return Totales

    def _es_exento(self):
        return self.l10n_latam_document_type_id.code in [32, 34, 41, 110, 111, 112] or (
            self.referencias and self.referencias[0].l10n_cl_reference_doc_type_selection in [32, 34, 41]
        )

    def _totales(self, MntExe=0, no_product=False, taxInclude=False):
        if self.move_type == 'entry' or self.is_outbound():
            sign = 1
        else:
            sign = -1
        MntNeto = 0
        IVA = False
        TasaIVA = False
        MntIVA = 0
        MntBase = 0
        if self._es_exento():
            MntExe = self.amount_total
            if no_product:
                MntExe = 0
            if self.amount_tax > 0:
                raise UserError("NO pueden ir productos afectos en documentos exentos")
        elif self.amount_untaxed and self.amount_untaxed != 0:
            IVA = False
            for t in self.line_ids:
                if t.tax_line_id.l10n_cl_sii_code in [14, 15]:
                    IVA = t
                for tl in t.tax_ids:
                    if tl.l10n_cl_sii_code in [14, 15]:
                        MntNeto += t.balance
                    if tl.l10n_cl_sii_code in [17]:
                        MntBase += t.balance  # @TODO Buscar forma de calcular la base para faenamiento
        if self.amount_tax == 0 and MntExe > 0 and not self._es_exento():
            raise UserError("Debe ir almenos un producto afecto")
        if MntExe > 0:
            MntExe = MntExe
        if IVA:
            TasaIVA = round(IVA.tax_line_id.amount, 2)
            MntIVA = IVA.balance
        if no_product:
            MntNeto = 0
            TasaIVA = 0
            MntIVA = 0
        MntTotal = self.amount_total
        if no_product:
            MntTotal = 0
        return MntExe, (sign * (MntNeto)), (sign * (MntIVA)), TasaIVA, MntTotal, (sign * (MntBase))

    def _validaciones_caf(self, caf):
        commercial_partner_id = self.commercial_partner_id or self.partner_id.commercial_partner_id
        if not commercial_partner_id.vat and not self._es_boleta() and not self._nc_boleta():
            raise UserError(_("Fill Partner VAT"))
        timestamp = self.time_stamp()
        invoice_date = self.invoice_date
        fecha_timbre = fields.Date.context_today(self)
        if fecha_timbre < invoice_date:
            raise UserError("La fecha de timbraje no puede ser menor a la fecha de emisión del documento")
        if fecha_timbre < date(int(caf["FA"][:4]), int(caf["FA"][5:7]), int(caf["FA"][8:10])):
            raise UserError("La fecha del timbraje no puede ser menor a la fecha de emisión del CAF")
        return timestamp


    def is_price_included(self):
        if not self.invoice_line_ids or not self.invoice_line_ids[0].tax_ids:
            return False
        tax = self.invoice_line_ids[0].tax_ids[0]
        if tax.price_include or (not tax.sii_detailed and (self._es_boleta() or self._nc_boleta())):
            return True
        return False

    def _invoice_lines(self):
        invoice_lines = []
        no_product = False
        MntExe = 0
        currency_base = self.currency_base()
        currency_id = self.currency_target()
        taxInclude = self.l10n_latam_document_type_id.es_boleta()
        # if (
        #     self.env["account.move.line"]
        #     .with_context(lang="es_CL")
        #     .search(["|", ("sequence", "=", -1), ("sequence", "=", 0), ("move_id", "=", self[0].id)])
        # ):
        #     self._onchange_invoice_line_ids()
        for line in self.with_context(lang="es_CL").invoice_line_ids:
            if not line.account_id:
                continue
            if line.product_id.default_code == "NO_PRODUCT":
                no_product = True
            lines = {}
            lines["NroLinDet"] = line.sequence
            if line.product_id.default_code and not no_product:
                lines["CdgItem"] = {}
                lines["CdgItem"]["TpoCodigo"] = "INT1"
                lines["CdgItem"]["VlrCodigo"] = line.product_id.default_code
            details = line.get_tax_detail()
            lines["Impuesto"] = details['impuestos']
            MntExe += details['MntExe']
            taxInclude = details['taxInclude']
            if details.get('cod_imp_adic'):
                lines['CodImpAdic'] = details['cod_imp_adic']
            if details.get('IndExe'):
                lines['IndExe'] = details['IndExe']
            # if line.product_id.move_type == 'events':
            #   lines['ItemEspectaculo'] =
            #            if self._es_boleta():
            #                lines['RUTMandante']
            lines["NmbItem"] = self._acortar_str(line.product_id.name, 80)  #
            lines["DscItem"] = self._acortar_str(line.name, 1000)  # descripción más extenza
            if line.product_id.default_code:
                lines["NmbItem"] = self._acortar_str(
                    line.product_id.name.replace("[" + line.product_id.default_code + "] ", ""), 80
                )
            # lines['InfoTicket']
            qty = round(line.quantity, 4)
            if not no_product:
                lines["QtyItem"] = qty
            if qty == 0 and not no_product:
                lines["QtyItem"] = 1
            elif qty < 0:
                raise UserError("NO puede ser menor que 0")
            if not no_product:
                uom_name = line.product_uom_id.with_context(exportacion=self.l10n_latam_document_type_id.es_exportacion()).name_get()
                lines["UnmdItem"] = uom_name[0][1][:4]
                price_unit = details['price_unit']
                lines["PrcItem"] = round(price_unit, 6)
                if currency_id:
                    lines["OtrMnda"] = {}
                    lines["OtrMnda"]["PrcOtrMon"] = round(
                        currency_base._convert(
                            price_unit, currency_id, self.company_id, self.invoice_date, round=False
                        ),
                        6,
                    )
                    lines["OtrMnda"]["Moneda"] = self._acortar_str(currency_id.name, 3)
                    lines["OtrMnda"]["FctConv"] = round(currency_id.rate, 4)
            if line.discount > 0:
                lines["DescuentoPct"] = line.discount
                DescMonto = line.discount_amount
                lines["DescuentoMonto"] = DescMonto
                if currency_id:
                    lines["DescuentoMonto"] = currency_base._convert(
                        DescMonto, currency_id, self.company_id, self.invoice_date
                    )
                    lines["OtrMnda"]["DctoOtrMnda"] = DescMonto
            if line.discount < 0:
                lines["RecargoPct"] = line.discount * -1
                RecargoMonto = line.discount_amount * -1
                lines["RecargoMonto"] = RecargoMonto
                if currency_id:
                    lines["OtrMnda"]["RecargoOtrMnda"] = currency_base._convert(
                        RecargoMonto, currency_id, self.company_id, self.invoice_date
                    )
            if not no_product and not taxInclude:
                price_subtotal = line.price_subtotal
                if currency_id:
                    lines["OtrMnda"]["MontoItemOtrMnda"] = currency_base._convert(
                        price_subtotal, currency_id, self.company_id, self.invoice_date
                    )
                lines["MontoItem"] = price_subtotal
            elif not no_product:
                price_total = line.price_total
                if currency_id:
                    lines["OtrMnda"]["MontoItemOtrMnda"] = currency_base._convert(
                        price_total, currency_id, self.company_id, self.invoice_date
                    )
                lines["MontoItem"] = price_total
            if no_product:
                lines["MontoItem"] = 0
            if lines["MontoItem"] < 0:
                raise UserError(_("No pueden ir valores negativos en las líneas de detalle"))
            if lines.get("PrcItem", 1) == 0:
                del lines["PrcItem"]
            invoice_lines.append(lines)
            if "IndExe" in lines:
                taxInclude = False
        return {
            "Detalle": invoice_lines,
            "MntExe": MntExe,
            "no_product": no_product,
            "tax_include": taxInclude,
        }

    def _acortar_str(self, texto, size=1):
        c = 0
        cadena = ""
        while c < size and c < len(texto):
            cadena += texto[c]
            c += 1
        return cadena

    def _gdr(self):
        result = []
        lin_dr = 1
        currency_base = self.currency_base()
        # for dr in self.global_descuentos_recargos:
        #     dr_line = {}
        #     dr_line["NroLinDR"] = lin_dr
        #     dr_line["TpoMov"] = dr.type
        #     if dr.gdr_detail:
        #         dr_line["GlosaDR"] = dr.gdr_detail
        #     disc_type = "%"
        #     if dr.gdr_type == "amount":
        #         disc_type = "$"
        #     dr_line["TpoValor"] = disc_type
        #     dr_line["ValorDR"] = currency_base.round(dr.valor)
        #     if self.currency_id != currency_base:
        #         currency_id = self.currency_id
        #         dr_line["ValorDROtrMnda"] = currency_base._convert(
        #             dr.valor, currency_id, self.company_id, self.invoice_date
        #         )
        #     if self.l10n_latam_document_type_id.l10n_cl_sii_code in [34] and (
        #         self.referencias and self.referencias[0].l10n_cl_reference_doc_type_selection == "34"
        #     ):  # solamente si es exento
        #         dr_line["IndExeDR"] = 1
        #     result.append(dr_line)
        #     lin_dr += 1
        return result

    def _dte(self, n_atencion=None):
        dte = {}
        invoice_lines = self._invoice_lines()
        dte["Encabezado"] = self._encabezado(
            invoice_lines["MntExe"], invoice_lines["no_product"],
            invoice_lines["tax_include"]
        )
        lin_ref = 1
        ref_lines = []
        if self._context.get("set_pruebas", False):
            RazonRef = "CASO"
            if not self._es_boleta() and n_atencion:
                RazonRef += " " + n_atencion
            RazonRef += "-" + str(self.sii_batch_number)
            ref_line = {}
            ref_line["NroLinRef"] = lin_ref
            if self._es_boleta():
                ref_line["CodRef"] = "SET"
            else:
                ref_line["TpoDocRef"] = "SET"
                ref_line["FolioRef"] = self.get_folio()
                ref_line["FchRef"] = datetime.strftime(datetime.now(), "%Y-%m-%d")
            ref_line["RazonRef"] = RazonRef
            lin_ref = 2
            ref_lines.append(ref_line)
        if self.referencias:
            for ref in self.referencias:
                ref_line = {}
                ref_line["NroLinRef"] = lin_ref
                if not self._es_boleta():
                    if self.get_converter_tipdoc(ref.l10n_cl_reference_doc_type_selection):
                        ref_line["TpoDocRef"] = (
                            self._acortar_str(self.get_converter_tipdoc(ref.l10n_cl_reference_doc_type_selection), 3)
                            if self.get_converter_tipdoc(ref.l10n_cl_reference_doc_type_selection)
                            else self.get_converter_tipdoc(ref.l10n_cl_reference_doc_type_selection)
                        )
                        ref_line["FolioRef"] = int(self.get_delete_str_car(ref.origin_doc_number))
                    ref_line["FchRef"] = ref.date or datetime.strftime(datetime.now(), "%Y-%m-%d")
                if ref.reference_doc_code not in ["", "none", False]:
                    ref_line["CodRef"] = ref.reference_doc_code
                ref_line["RazonRef"] = ref.reason
                if self._es_boleta():
                    ref_line['CodVndor'] = self.user_id.id
                    ref_lines["CodCaja"] = self.journal_id.point_of_sale_id.name
                ref_lines.append(ref_line)
                lin_ref += 1
        dte["Detalle"] = invoice_lines["Detalle"]
        dte["DscRcgGlobal"] = self._gdr()
        dte["Referencia"] = ref_lines
        dte["CodIVANoRec"] = self.no_rec_code
        dte["IVAUsoComun"] = self.iva_uso_comun
        dte["moneda_decimales"] = self.currency_id.decimal_places
        return dte

    def _es_boleta(self):
        return self.l10n_latam_document_type_id.es_boleta()

    def get_delete_str_car(self,value):
        numeros =['0','1','2','3','4','5','6','7','8','9']
        nueva = '0'
        cont = 0
        for letra in value:
            if letra in numeros:
                cont+=1
                if cont <=10:
                    nueva += letra
        return nueva

    def get_converter_tipdoc(self,value):
        vals = {
            '29':'29',
            '30':'30',
            '32':'32',
            '33':'33',
            '34':'34',
            '35':'35',
            '38':'38',
            '39':'39',
            '40':'40',
            '41':'41',
            '43':'43',
            '45':'45',
            '46':'46',
            '50':'48',
            '52':'53',
            '55':'55',
            '56':'56',
            '60':'60',
            '61':'61',
            '70':'101',
            '71':'102',
            '103':'103',
            '108':'104',
            '110':'105',
            '111':'106',
            '112':'108',
            '500':'109',
            '501':'110',
            '801':'111',
            '802':'112',
            '803':'175',
            '804':'180',
            '805':'185',
            '806':'900',
            '807':'901',
            '808':'902',
            '809':'903',
            '810':'904',
            '811':'905',
            '812':'906',
            '813':'907',
            '814':'909',
            '815':'910',
            '901':'911',
            '902':'914',
            '903':'918',
            '904':'919',
            '905':'920',
            '906':'921',
            '907':'922',
            '911':'924',
            '914':'500',
            '919':'501',
            'HEM':'HEM',
            'HES':'HES',
            'MIG':'MIG',
            'CHQ':'CHQ',
            'PAG':'PAG',
        }
        return vals[value]

# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
import decimal



class AccountInvoiceLine(models.Model):
    _inherit = "account.move.line"

    sequence = fields.Integer(string="Sequence", default=-1,)
    discount_amount = fields.Float(string="Monto Descuento", default=0.00,)

    @api.onchange("discount", "price_unit", "quantity")
    def set_discount_amount(self):
        total = self.currency_id.round(self.quantity * self.price_unit)
        decimal.getcontext().rounding = decimal.ROUND_HALF_UP
        self.discount_amount = int(decimal.Decimal(total * ((self.discount or 0.0) / 100.0)).to_integral_value())


    @api.depends(
        "price_unit",
        "discount",
        "tax_ids",
        "quantity",
        "product_id",
        "move_id.partner_id",
        "move_id.currency_id",
        "move_id.company_id",
        "move_id.date",
        "move_id.date",
    )
    def _compute_price(self):
        for line in self:
            line.set_discount_amount()
            continue
            currency = line.move_id and line.move_id.currency_id or None
            taxes = False
            total = 0
            included = False
            #@dar soporte a mepco con nueva estructura
            #for t in line.tax_ids:
            #    if t.product_uom_id and t.product_uom_id.category_id != line.product_uom_id.category_id:
            #        raise UserError("Con este tipo de impuesto, solamente deben ir unidades de medida de la categoría %s" %t.product_uom_id.category_id.name)
            #    if t.mepco:
            #        t.verify_mepco(line.move_id.date, line.move_id.currency_id)
            #    if taxes and (t.price_include != included):
            #        raise UserError('No se puede hacer timbrado mixto, todos los impuestos en este pedido deben ser uno de estos dos:  1.- precio incluído, 2.-  precio sin incluir')
            #    included = t.price_include
            #    taxes = True
            taxes = line.tax_ids.compute_all(
                line.price_unit,
                currency,
                line.quantity,
                product=line.product_id,
                partner=line.move_id.partner_id,
                discount=line.discount, uom_id=line.product_uom_id)
            if taxes:
                line.price_subtotal = price_subtotal_signed = taxes['total_excluded']
            else:
                total = line.currency_id.round((line.quantity * line.price_unit))
                decimal.getcontext().rounding = decimal.ROUND_HALF_UP
                total = line.currency_id.round((line.quantity * line.price_unit)) - line.discount_amount
                line.price_subtotal = price_subtotal_signed = int(decimal.Decimal(total).to_integral_value())
            if self.move_id.currency_id and self.move_id.currency_id != self.move_id.company_id.currency_id:
                currency = self.move_id.currency_id
                date = self.move_id._get_currency_rate_date()
                price_subtotal_signed = currency._convert(
                    price_subtotal_signed,
                    self.move_id.company_id.currency_id,
                    self.company_id or self.env.user.company_id,
                    date or fields.Date.today(),
                )
            sign = line.move_id.type in ["in_refund", "out_refund"] and -1 or 1
            line.price_subtotal_signed = price_subtotal_signed * sign
            line.price_total = taxes["total_included"] if (taxes and taxes["total_included"] > total) else total


    def get_tax_detail(self):
        boleta = self.move_id.l10n_latam_document_type_id.es_boleta()
        nc_boleta = self.move_id._nc_boleta()
        amount_total = 0
        details = dict(
            impuestos=[],
            taxInclude=False,
            MntExe=0,
            price_unit=self.price_unit,
        )
        currency_base = self.move_id.currency_base()
        for t in self.tax_ids:
            if not boleta and not nc_boleta:
                if t.l10n_cl_sii_code in [26, 27, 28, 35, 271]:#@Agregar todos los adicionales
                    details['cod_imp_adic'] = t.l10n_cl_sii_code
            details['taxInclude'] = t.price_include
            if t.amount == 0 or t.l10n_cl_sii_code in [0]:#@TODO mejor manera de identificar exento de afecto
                details['IndExe'] = 1#line.product_id.ind_exe or 1
                details['MntExe'] += currency_base.round(self.price_subtotal)
            else:
                if boleta or nc_boleta:
                    amount_total += self.price_total
                amount = t.amount
                if t.l10n_cl_sii_code in [28, 35]:
                    amount = t.compute_factor(self.product_uom_id)
                details['impuestos'].append({
                            "CodImp": t.l10n_cl_sii_code,
                            'price_include': details['taxInclude'],
                            'TasaImp': amount,
                        }
                )
        if amount_total > 0:
            details['impuestos'].append({
                    'name': t.description,
                    "CodImp": t.l10n_cl_sii_code,
                    'price_include': boleta or nc_boleta or details['taxInclude'],
                    'TasaImp': amount,
                }
            )
            if not details['taxInclude'] and (boleta or nc_boleta):
                taxes_res = self._get_price_total_and_subtotal_model(
                    self.price_unit,
                    1,
                    self.discount,
                    self.move_id.currency_id,
                    self.product_id,
                    self.move_id.partner_id,
                    self.tax_ids,
                    self.move_id.move_type)
                details['price_unit'] = taxes_res.get('price_total', 0.0)
        if boleta or nc_boleta:
             details['taxInclude'] = True
        return details
