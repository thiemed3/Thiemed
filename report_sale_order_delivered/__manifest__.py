# -*- coding: utf-8 -*-
{
    'name': "Report sale order delivered",
    'summary': """Reporte de ventas en base a productos entregados""",
    'description': "",
    'author': "Tierranube(Nestor Ulloa)",
    'website': "http://www.tierranube.cl",
    'license': 'LGPL-3',
    'category': 'sale',
    'version': '18.0.0.1',
    # any module necessary for this one to work correctly
    'depends': ['base', 'sale', 'sale_order_medical_information'],
    # always loaded
    'data': [
        'report/sale_report_delivered.xml',
        'report/report_sale_view.xml',
    ],
    # only loaded in demonstration mode
    'demo': [],
    #'demo.xml',
    'installable': True,
    'application': False,
    'auto_install': False,
}