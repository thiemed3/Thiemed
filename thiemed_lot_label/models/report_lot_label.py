from odoo import models

class ReportThiemedLotLabel(models.AbstractModel):
    _name = "report.thiemed.label_lot_70x30_zpl"
    _description = "Etiqueta Thiemed de lote 70x30 ZPL"

    def _get_report_values(self, docids, data=None):
        docs = self.env["stock.lot"].browse(docids)
        data = data or {}
        try:
            quantity = int(data.get("quantity", 1))
        except (TypeError, ValueError):
            quantity = 1
        quantity = max(quantity, 1)
        return {
            "doc_ids": docs.ids,
            "doc_model": "stock.lot",
            "docs": docs,
            "quantity": quantity,
            "copies": range(quantity),
        }
