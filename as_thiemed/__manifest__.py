# -*- coding: utf-8 -*-
{
    'name': "Ahorasoft Thiemed Project",
    'category': 'Thiemed',
    'version': '1.1.2',
    'author': "Ahorasoft",
    'website': 'http://www.ahorasoft.com',
    "support": "soporte@ahorasoft.com",
    'summary': """
        Ahorasoft Thiemed Project""",
    'description': """
        Ahorasoft Thiemed Project
    """,
    "images": [],
    "depends": [
        "base","stock","product","report_xlsx","account",'l10n_cl_balance','account'
    ],
    'data': [
        'security/ir.model.access.csv',
        # 'wizard/as_kardex_productos_wiz.xml',
        # 'wizard/as_cambiador_factura.xml',
        # 'views/as_res_config.xml',
        # 'views/as_stock_picking.xml',
        # 'views/as_production_lot_tree.xml',
        # 'views/as_pricelist_item.xml',
    ],
    'qweb': [
    ],
    # 'demo': [
    #     'demo/demo.xml',
    # ],
    'installable': True,
    'auto_install': False,
    
}