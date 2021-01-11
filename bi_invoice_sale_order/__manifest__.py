# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Invoice from Sale Order',
    'version': '11.0.0.4',
    'category': 'Accounting',
    'summary': 'This apps create invoice from Sale Order and add Picking to invoice',
    'description': """
    Invoice from Sale Order and add Picking to invoice
""",
    'author': 'Odoo Latam',
    #'price': '35.00',
    #'currency': "EUR",
    'website': 'http://www.odoolatam.com',
    'depends': ['sale','purchase','stock','l10n_cl_sale_order_references'],
    # 'data': ['picking_view.xml'
    # ],
    'demo': [],
    'js': [],
    'qweb': [],
    'installable': True,
    'auto_install': False,
    "images":['static/description/Banner.png'],
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
