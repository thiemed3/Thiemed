{
    'name': "Homologación de Productos - CRM",
    'summary': "Integración de precotizaciones de homologación con oportunidades CRM",
    'author': "Tierranube",
    'website': "http://www.tierranube.cl",
    'category': 'Sales',
    'version': '19.0.1.0.0',
    'depends': ['product_homologation', 'crm'],
    'data': [
        'views/crm_lead_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': True,
}
