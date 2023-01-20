# -*- coding: utf-8 -*-
{
    'name': "sale_order_line_check",
    'summary': """Check para validar impresion en la linea del pedido""",
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
    'depends': ['base', 'sale'],
    # always loaded
    'data': [
        'views/sale_order_line_check.xml',
        'report/sale_report_templates.xml'
    ],
    # only loaded in demonstration mode
    'demo': [],
    #'demo.xml',
    'installable': True,
    'application': False,
    'auto_install': False,
}