
{
    'name': "Sale Order Medical Information",
    'category': 'sale',
    'version': '17.0.1.0',
    'author': 'Nestor Ulloa - Tierranube',
    'description': """
        
    """,
    'summary': """""",
    'depends': ['base', 'sale', 'sale_management', 'sale_stock'],
    'price': 25,
    'currency': 'EUR',
    'license': 'OPL-1',
    'website': "",
    'data': [
        'views/sale_order_doc.xml',
        'views/stock_picking_doc.xml',
        'views/account_move.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}

