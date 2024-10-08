# -*- coding: utf-8 -*-
{
    'name': 'AhoraSoft Modulo THIEMED en facturas',
    'version': '1.0.8',
    'category': 'sale',
    'author': 'Ahorasoft',
    'summary': 'Customized invoice Management',
    'website': 'http://www.ahorasoft.com',
    'depends': [
        'base',
        'sale','product', 'account','stock','l10n_cl_edi','stock_landed_costs','mrp'
    ],
    'data': [
        # 'security/as_group_view.xml',

        'security/ir.model.access.csv',
        'views/sale_order.xml',
        # 'views/sii_document_class_view.xml',
        'views/as_stock_picking.xml',
        'views/as_pricelist_item.xml',
        'views/stock_landed_cost_views.xml',
        'views/as_res_config.xml',
        #'wizard/as_kardex_productos_wiz.xml',
        # 'data/res_config_settings.yml',
        'data/res_users_data.xml',
        'data/stock_landed_cost_data.xml',
        'views/report/as_report_templates.xml',
        'views/as_report_format.xml',
        'views/as_stock_production_lot.xml',

        # 'views/as_tabla_comisiones.xml',
        # 'views/as_res_config.xml',
        # 'views/as_product_pricelist.xml',
        # 'views/sale_order_inherit_view.xml',
        # 'views/as_product_template.xml',
        # 'views/as_partner.xml',

    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}