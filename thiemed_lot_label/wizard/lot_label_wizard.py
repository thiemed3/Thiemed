from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class ThiemedLotLabelWizard(models.TransientModel):
    _name = "thiemed.lot.label.wizard"
    _description = "Imprimir etiquetas Thiemed de lote"

    lot_ids = fields.Many2many("stock.lot", string="Lotes", required=True)
    quantity = fields.Integer(string="Cantidad de etiquetas por lote", default=1, required=True)

    @api.model
    def default_get(self, field_list):
        values = super().default_get(field_list)
        if self.env.context.get("active_model") == "stock.lot":
            active_ids = self.env.context.get("active_ids") or []
            if active_ids:
                values["lot_ids"] = [(6, 0, active_ids)]
        return values

    @api.constrains("quantity")
    def _check_quantity(self):
        for rec in self:
            if rec.quantity < 1:
                raise ValidationError(_("La cantidad debe ser al menos 1."))

    def action_print(self):
        self.ensure_one()
        report = self.env["ir.actions.report"].search([
            ("report_name", "=", "thiemed.label_lot_70x30_zpl"),
            ("model", "=", "stock.lot"),
        ], limit=1)
        if not report:
            raise UserError(_("No se encontró el informe Etiqueta Thiemed 70x30 (ZPL)."))
        return report.report_action(self.lot_ids, data={"quantity": self.quantity})
