# -*- coding: utf-8 -*-
{
    'name': 'Customizaciones Guia de Despacho',
    'version': '1.0.1',
    'category': 'stock',
    'summary': 'Customizaciones Guia de Despacho Lozalizacion Chilena',
    'description': """
    Customizaciones Guia de Despacho Lozalizacion Chilena
""",
    'author': 'Odoo Latam',
    'website': 'http://www.ahorasoft.com',
    'depends': ['product','stock','account','l10n_cl_edi_stock'],
    'data': [
        'views/picking_view.xml', 
        'views/report/as_picking_cedible.xml', 
        'views/report/as_picking_report.xml', 
        ],
    'demo': [],
    'js': [],
    'qweb': [],
    'installable': True,
    'auto_install': False,
}

