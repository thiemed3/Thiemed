# -*- coding: utf-8 -*-
# from odoo import http


# class L10nClEdiStockDeliveryGuide(http.Controller):
#     @http.route('/l10n_cl_edi_stock_delivery_guide/l10n_cl_edi_stock_delivery_guide/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/l10n_cl_edi_stock_delivery_guide/l10n_cl_edi_stock_delivery_guide/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('l10n_cl_edi_stock_delivery_guide.listing', {
#             'root': '/l10n_cl_edi_stock_delivery_guide/l10n_cl_edi_stock_delivery_guide',
#             'objects': http.request.env['l10n_cl_edi_stock_delivery_guide.l10n_cl_edi_stock_delivery_guide'].search([]),
#         })

#     @http.route('/l10n_cl_edi_stock_delivery_guide/l10n_cl_edi_stock_delivery_guide/objects/<model("l10n_cl_edi_stock_delivery_guide.l10n_cl_edi_stock_delivery_guide"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('l10n_cl_edi_stock_delivery_guide.object', {
#             'object': obj
#         })
