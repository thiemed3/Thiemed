import logging

from odoo import SUPERUSER_ID, models

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    def get_digital_signature(self, company_id):
        user_id = self.id
        if user_id == SUPERUSER_ID:
            user_id = self.env.ref("base.user_admin").id
        signature = self.env["sii.firma"].search(
            [
                ("user_ids", "child_of", [user_id]),
                ("company_ids", "child_of", [company_id.id]),
                ("state", "=", "valid"),
            ],
            limit=1,
            order="priority ASC",
        )
        if signature:
            signature.check_signature()
            if signature.active:
                return signature
        return self.env["sii.firma"]

class Certificate(models.Model):
    _inherit = 'l10n_cl.certificate'

    def parametros_firma(self):
        return {
            "priv_key": self.private_key,
            "cert": self.certificate,
            "rut_firmante": self.subject_serial_number,
            "init_signature": False,
        }

class l10n_latamdocumenttype(models.Model):
    _inherit = 'l10n_latam.document.type'

    def es_boleta(self):
        if self.code in [35, 38, 39, 41, 70, 71]:
            return True
        return False

    def es_nc_boleta(self):
        if self.code in [35, 38, 39, 41, 70, 71]:
            return True
        return False

    def es_nc_exportacion(self):
        return self.code in [111, 112]

    def es_exportacion(self):
        return self.code in [110] or self.es_nc_exportacion()
