# -*- coding: utf-8 -*-
{
    'name': 'TPCO Customizaciones Consumo de Folio',
    'version': '1.0.1',
    'category': 'stock',
    'summary': 'TPCO Customizaciones Consumo de Folio Lozalizacion Chilena',
    'description': """
    TPCO Customizaciones Consumo de Folio Lozalizacion Chilena
""",
    'author': 'tpco',
    'website': 'http://www.tpco.cl',
    'depends': ['product','stock','account','l10n_cl_edi','l10n_cl','account'],
    'data': [
        'security/ir.model.access.csv', 
        'views/libro_compra_venta.xml', 
        'views/consumo_folios.xml', 
        'views/sii_xml_envio.xml', 
        'views/sii_cola_envio.xml', 
        'data/cron.xml',
        ],
    'demo': [],
    'js': [],
    'qweb': [],
    'installable': True,
    'auto_install': False,
}

