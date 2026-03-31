from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def copy(self, default=None):
        self.ensure_one()

        new_order = super().copy(default)

        # Publica una nota interna en el pedido duplicado
        new_order.message_post_with_source(
            "sale_order_duplicate_message.sale_order_duplicate_origin_message",
            render_values={
                "origin": self,
            },
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )

        return new_order