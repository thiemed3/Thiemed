{
    'name': "Referencias en stock",
    'category': 'stock',
    'version': '14.0.1.0',
    'author': 'Pedro Arroyo - Tierranube',
    'description': """

    """,
    'summary': """""",
    'depends': ['base','stock', 'l10n_cl_edi_stock', 'sale'],
    'currency': 'CLP',
    'license': 'OPL-1',
    'website': "",
    'data': [
        'views/stock_picking.xml',
        'views/report_delivery_guide.xml',
        'views/dte_template.xml',
        # 'views/sale_order.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}


