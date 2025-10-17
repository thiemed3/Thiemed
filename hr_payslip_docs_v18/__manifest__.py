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
        * Probado con localización Chile (l10n_cl)

        Autor: Natalie Aliaga
        Sitio: https://www.tierranube.cl
    """,
    "version": "18.0.1.0",  # Buena práctica cambiar la versión al hacer cambios
    "author": "Natalie Aliaga",
    "website": "https://www.tierranube.cl",
    "license": "LGPL-3",
    "category": "Human Resources/Payroll",
    "depends": [
        "hr_payroll",  # Base de Nóminas
        "documents",  # Para guardar el PDF
        "mail",  # Para enviar el correo
        "base_automation",  # Para las acciones automáticas
        "l10n_cl_hr_payroll",  # Lógica y reglas de la nómina de Chile
        "l10n_cl_hr_payroll_reports",  # Plantilla del reporte PDF de la nómina de Chile
    ],
    "data": [
        # Seguridad (siempre primero)
        "security/ir.model.access.csv",
        "security/hr_payslip_security.xml",

        # Datos y configuración
        "data/mail_template.xml",
        "data/payslip_actions.xml",
        "data/automation.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
