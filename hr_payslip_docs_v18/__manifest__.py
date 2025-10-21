# -*- coding: utf-8 -*-
{
    'name': 'Gestión Automática de Recibos de Nómina (CL)',
    'summary': "Genera PDF de nómina, lo archiva en Documentos y lo envía por correo al confirmar la nómina.",
    'description': """
        Módulo complementario para Odoo 18 -Payroll Chile
        * Generación automática de PDF al confirmar (estado 'done')
        * Guarda en Documentos (carpeta 'Nóminas')
        * Envío por correo al empleado
        * Acciones manuales desde listado
        * Seguridad por empleado
    """,
    'version': '18.0.1.0',
    'author': 'Natalie Aliaga',
    'website': 'https://www.tierranube.cl',
    'license': 'LGPL-3',
    'category': 'Human Resources/Payroll',
    'depends': [
        'base',
        'mail',
        'hr',
        'hr_payroll',
        'documents',

    ],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_template.xml',
        'data/payslip_actions.xml',
        'data/cron.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
