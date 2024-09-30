{
    'name': "Account Lot Expiration Reports",
    'summary': """Modulo que muestra los lotes de los productos en el reporte de Facturacion y Guia de despacho,
                Se agrega tambien los datos de la cirugia en los reportes de Facturacion y Guia de despacho""",
    'description': "",
    'author': "Tierranube(Nestor Ulloa)",
    'website': "http://www.tierranube.cl",
    'license': 'LGPL-3',
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'sale',
    'version': '1.1',
    # any module necessary for this one to work correctly
    'depends': ['base',
                'account',
                'l10n_cl',
                'stock',
                'sale',
                'l10n_cl_edi_stock',
                'l10n_cl_edi_stock_delivery_guide',
                'stock_account',
                'sale_stock',
                'product_expiry',
            ],
    # always loaded
    'data': [
        'reports/report_delivery_guide.xml',
        'reports/report_invoice.xml',
        # 'views/stock_picking_views.xml',
        # 'views/sale_order_views.xml',
        # 'views/account_move_views.xml',
        'views/move_line_ids_views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
