import logging
from lxml import etree
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _
import json

server_url = {
    'SIITEST': 'https://maullin.sii.cl/DTEWS/',
    'SII': 'https://palena.sii.cl/DTEWS/',
}

CLAIM_URL = {
    'SIITEST': 'https://ws2.sii.cl/WSREGISTRORECLAMODTECERT/registroreclamodteservice',
    'SII': 'https://ws1.sii.cl/WSREGISTRORECLAMODTE/registroreclamodteservice',
}

_logger = logging.getLogger(__name__)

try:
    from facturacion_electronica import facturacion_electronica as fe
except Exception as e:
    _logger.warning("no se ha cargado FE %s" % str(e))
try:
    from suds.client import Client
except:
    _logger.warning("no se ha cargado suds")
try:
    import xmltodict
except ImportError:
    _logger.info('Cannot import xmltodict library')

status_dte = [
    ("no_revisado", "No Revisado"),
    ("0", "Conforme"),
    ("1", "Error de Schema"),
    ("2", "Error de Firma"),
    ("3", "RUT Receptor No Corresponde"),
    ("90", "Archivo Repetido"),
    ("91", "Archivo Ilegible"),
    ("99", "Envio Rechazado - Otros"),
]


class SIIXMLEnvio(models.Model):
    _name = "sii.xml.envio"
    _description = "XML de envío DTE"
    _inherit = ['l10n_cl.edi.util']

    name = fields.Char(string="Nombre de envío", required=True, readonly=True, states={"draft": [("readonly", False)]},)
    xml_envio = fields.Text(string="XML Envío", required=True, readonly=True, states={"draft": [("readonly", False)]},)
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("NoEnviado", "No Enviado"),
            ("Enviado", "Enviado"),
            ("Aceptado", "Aceptado"),
            ("Rechazado", "Rechazado"),
        ],
        default="draft",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañia",
        required=True,
        default=lambda self: self.env.user.company_id.id,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    sii_xml_response = fields.Text(
        string="SII XML Response", copy=False, readonly=True, states={"NoEnviado": [("readonly", False)]},
    )
    l10n_cl_sii_send_ident = fields.Text(
        string="SII Send Identification", copy=False, readonly=True, states={"draft": [("readonly", False)]},
    )
    sii_receipt = fields.Text(
        string="SII Mensaje de recepción",
        copy=False,
        readonly=False,
        states={"Aceptado": [("readonly", False)], "Rechazado": [("readonly", False)]},
    )
    user_id = fields.Many2one(
        "res.users",
        string="Usuario",
        helps="Usuario que envía el XML",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    move_ids = fields.One2many(
        "account.move", "sii_xml_request", string="Facturas", readonly=True, states={"draft": [("readonly", False)]},
    )
    attachment_id = fields.Many2one("ir.attachment", string="XML Recepción", readonly=True,)
    email_respuesta = fields.Text(string="Email SII", readonly=True,)
    email_estado = fields.Selection(status_dte, string="Respuesta Envío", readonly=True,)
    email_glosa = fields.Text(string="Glosa Recepción", readonly=True,)

    def create_template_seed(self, seed):
        xml = u'''<getToken>
<item>
<Semilla>{}</Semilla>
</item>
</getToken>
'''.format(seed)
        return xml

    def get_seed(self, company_id):
        try:
            import ssl
            ssl._create_default_https_context = ssl._create_unverified_context
        except:
            pass
        url = server_url[company_id.l10n_cl_dte_service_provider] + 'CrSeed.jws?WSDL'
        _server = Client(url)
        try:
            resp = _server.service.getSeed().replace('<?xml version="1.0" encoding="UTF-8"?>','')
        except Exception as e:
            _logger.warning(e)
            if str(e) == "(503, 'Service Temporarily Unavailable')":
                raise UserError(_("Conexión SII no disponible, intente otra vez"))
            else:
                raise UserError(str(e))
        root = etree.fromstring(resp)
        semilla = root[0][0].text
        return semilla

    def sign_seed(self, message, privkey, cert):
        return self.env['account.move.book'].sign_seed(message, privkey, cert)

    def get_token(self, user_id, company_id):
        signature_id = self.company_id._get_digital_signature(user_id=self.env.user.id)
        return self._get_token(self.company_id.l10n_cl_dte_service_provider, signature_id)


    def name_get(self):
        result = []
        for r in self:
            name = r.name + " Código Envío: %s" % r.l10n_cl_sii_send_ident if r.l10n_cl_sii_send_ident else r.name
            result.append((r.id, name))
        return result


    def unlink(self):
        for r in self:
            if r.state in ["Aceptado", "Enviado"]:
                raise UserError(_("You can not delete a valid document on SII"))
        return super(SIIXMLEnvio, self).unlink()

    def _emisor(self):
        Emisor = {}
        Emisor["RUTEmisor"] = self.company_id.partner_id.vat
        Emisor["RznSoc"] = self.company_id.name
        Emisor["Modo"] = "produccion" if self.company_id.l10n_cl_dte_service_provider == "SII" else "certificacion"
        Emisor["NroResol"] = self.company_id.l10n_cl_dte_resolution_number
        Emisor["FchResol"] = self.company_id.l10n_cl_dte_resolution_date.strftime("%Y-%m-%d")
        Emisor["ValorIva"] = 19
        return Emisor

    def _get_datos_empresa(self, company_id):
        signature_id = self.company_id._get_digital_signature(user_id=self.env.user.id)
        if not signature_id:
            raise UserError(
                _(
                    """There are not a Signature Cert Available for this user, please upload your signature or tell to someelse."""
                )
            )
        emisor = self._emisor()
        return {
            "Emisor": emisor,
            "firma_electronica": signature_id.parametros_firma(),
        }


    def send_xml(self):
        if self.l10n_cl_sii_send_ident:
            _logger.warning("XML %s ya enviado" % self.name)
            return
        datos = self._get_datos_empresa(self.company_id)
        datos.update(
            {"sii_xml_request": self.xml_envio, "filename": self.name, "api": "EnvioBOLETA" in self.xml_envio,}
        )
        res = fe.enviar_xml(datos)
        self.write(
            {
                "state": res.get("status", "NoEnviado"),
                "l10n_cl_sii_send_ident": res.get("sii_send_ident", ""),
                "sii_xml_response": res.get("sii_xml_response", ""),
            }
        )
        self.set_states()

    def do_send_xml(self):
        self.send_xml()

    def object_receipt(self):
        if '<?xml' in self.sii_receipt:
            return etree.XML(
                self.sii_receipt.replace('<?xml version="1.0" encoding="UTF-8"?>', "")
                .replace("SII:", "")
                .replace(' xmlns="http://www.sii.cl/XMLSchema"', "")
            )
        return json.loads(self.sii_receipt)

    # def get_send_status(self, user_id=False):
    #     datos = self._get_datos_empresa(self.company_id)
    #     api = "EnvioBOLETA" in self.xml_envio
    #     if self._context.get("set_pruebas", False):
    #         api = False
    #     datos.update(
    #         {"codigo_envio": self.l10n_cl_sii_send_ident, "api": api,}
    #     )
    #     res = fe.consulta_estado_dte(datos)
    #     self.write(
    #         {"state": res["status"], "sii_receipt": res.get("xml_resp", False),}
    #     )
    #     self.set_states()

    def get_send_status(self, user_id=False):
        user_id = user_id or self.user_id
        token = self.get_token(user_id, self.company_id)
        url = server_url[self.company_id.l10n_cl_dte_service_provider] + 'QueryEstUp.jws?WSDL'
        _server = Client(url)
        rut = self.move_ids._l10n_cl_format_vat( self.company_id.vat)
        respuesta = _server.service.getEstUp(
                rut[:8].replace('-', ''),
                str(rut[-1]),
                self.l10n_cl_sii_send_ident,
                token,
            )
        result = {"sii_receipt" : respuesta}
        resp = xmltodict.parse(respuesta)
        result.update({"state": "Enviado"})
        if resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] == "-11":
            if resp['SII:RESPUESTA']['SII:RESP_HDR']['ERR_CODE'] == "2":
                status = {'warning':{'title':_('Estado -11'), 'message': _("Estado -11: Espere a que sea aceptado por el SII, intente en 5s más")}}
            else:
                _logger.warning(_("Estado -11: error 1Algo a salido mal, revisar carátula"))
                result.update({'state': 'Rechazado'})
        if resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] in ["EPR", "LOK"]:
            result.update({"state": "Aceptado"})
            if resp['SII:RESPUESTA'].get('SII:RESP_BODY') and resp['SII:RESPUESTA']['SII:RESP_BODY']['RECHAZADOS'] == "1":
                result.update({ "state": "Rechazado" })
        elif resp['SII:RESPUESTA']['SII:RESP_HDR']['ESTADO'] in ["RCT", "RFR", "LRH", "RCH", "RSC"]:
            result.update({"state": "Rechazado"})
            _logger.warning(resp)
        self.write(result)


    def ask_for(self):
        self.ask_for_dte_status()

    def l10n_cl_verify_dte_status(self, send_dte_to_partner=True): 
        digital_signature = self.company_id._get_digital_signature(user_id=self.env.user.id)
        response = self._get_send_status(
            self.company_id.l10n_cl_dte_service_provider,
            self.l10n_cl_sii_send_ident,
            self._l10n_cl_format_vat(self.company_id.vat),
            digital_signature)
        if not response:
            self.l10n_cl_dte_status = 'ask_for_status'
            digital_signature.last_token = False
            return None

        
    def ask_for_dte_status(self):
        self.l10n_cl_verify_dte_status(False)
        
    def set_childs(self, state):
        for r in self.move_ids:
            r.sii_result = state

    @api.onchange('state')
    def set_states(self):
        state = self.state
        if state in ['draft', 'NoEnviado']:
            return
        if self.sii_receipt:
            receipt = self.object_receipt()
            if type(receipt) is dict:
                if not receipt.get('estadistica'):
                    state = 'Aceptado'
            elif receipt.find("RESP_HDR") is not None:
                state = "Aceptado"
        self.set_childs(state)
