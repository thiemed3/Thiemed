# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_cl_delivery_guide_price_list = fields.Selection([
        ('product_price', 'Product Price'),
        ('sale_order_price', 'In Sale Order'),
        ('no_price', 'No Price')
    ], string='Delivery Guide Price List', default='product_price')

    def _l10n_cl_is_delivery_guide_with_product_price_lst(self):
        return self.l10n_cl_delivery_guide_price_list == 'product_price'

    def _l10n_cl_is_delivery_guide_with_sale_order_price(self):
        return self.l10n_cl_delivery_guide_price_list == 'sale_order_price'

    def _l10n_cl_is_delivery_guide_with_no_price(self):
        return self.l10n_cl_delivery_guide_price_list == 'no_price'


