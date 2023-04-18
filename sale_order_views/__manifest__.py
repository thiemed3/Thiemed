{
    'name': "Sale Order Views",
    'summary': """Modulo para liminar la creacion de productos y clientes desde la vista de ventas""",
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
    'depends': ['base', 'sale'],
    # always loaded
    'data': [
        'views/sale_order_view.xml',
    ],
    # only loaded in demonstration mode
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
