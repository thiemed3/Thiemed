# -*- coding: utf-8 -*-
{
    "name": "Gestión Automática de Recibos de Nómina (CL)",
    "summary": """
        Genera PDF de nómina automáticamente, lo archiva en Documentos 
        y lo envía por correo al empleado al confirmar la nómina.
    """,
    "description": """
        Módulo complementario para Odoo 18 Enterprise - Payroll Chile
        ================================================================
        
        Funcionalidades:
        ----------------
        * Generación automática de PDF de nómina al confirmar (estado 'done')
        * Creación de documento en la app Documentos (carpeta 'Nóminas')
        * Envío automático por correo al empleado
        * Acciones manuales disponibles desde listado de nóminas
        * Control de idempotencia (no duplica documentos ni correos)
        * Seguridad: empleados solo ven sus propios documentos
        
        Compatibilidad:
        ---------------
        * Odoo 18.0 Enterprise
        * Requiere: hr_payroll, documents, mail
        * Probado con localización Chile (l10n_cl)
        
        Autor: Natalie Aliaga
        Sitio: https://www.tierranube.cl
    """,
    "version": "18.0",
    "author": "Natalie Aliaga",
    "website": "https://www.tierranube.cl",
    "license": "LGPL-3",
    "category": "Human Resources/Payroll",
    "depends": [
        "hr_payroll",      # Módulo base de nómina
        "hr_contract_history",
        "hr_payroll_portal",
        "l10n_cl_hr",
        "l10n_cl_hr_payroll",
        "l10n_cl_hr_payroll_reports",
        "documents",       # App Documentos (Enterprise)
        "mail",           # Sistema de correo
        "base_automation", # Automatizaciones
        "account_monetary_correction",
    ],
    "data": [
        # Seguridad (siempre primero)
        "security/ir.model.access.csv",
        "security/hr_payslip_security.xml",
        
        # Datos y configuración
        "data/mail_template.xml",
        "data/payslip_actions.xml",
        "data/automation.xml",
        
        # Vistas (si las hay)
        # "views/hr_payslip_views.xml",
    ],
    "demo": [],
    "images": [],
    "installable": True,
    "application": False,
    "auto_install": False,  # Cambiado a False para instalación manual
    "external_dependencies": {
        "python": [],
    },
}
