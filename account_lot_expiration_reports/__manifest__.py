{
    'name': "Account Lot Expiration Reports",
    'summary': """Modulo que muestra los lotes de los productos en el reporte de Facturacion y Guia de despacho""",
    'description': "",
    'author': "Tierranube(Nestor Ulloa)",
    'website': "http://www.tierranube.cl",
    'license': 'LGPL-3',
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'sale',
    'version': '1.0',
    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'stock', 'l10n_cl_edi_stock_delivery_guide', 'account', 'l10n_cl'],
    # always loaded
    'data': [
        'reports/report_delivery_guide.xml',
        'reports/report_invoice.xml',
    ],
    # only loaded in demonstration mode
    'demo': [],
    #'demo.xml',
    'installable': True,
    'application': False,
    'auto_install': False,
}
