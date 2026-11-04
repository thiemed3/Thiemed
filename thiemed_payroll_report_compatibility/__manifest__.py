{
    "name": "Thiemed - Compatibilidad de reportes de remuneraciones",
    "version": "19.0.1.0.1",
    "category": "Human Resources/Payroll",
    "author": "Tierra Nube",
    "summary": "Acceso seguro a Nómina general y Certificado de Antigüedad",
    "description": "Reutiliza los reportes de remuneraciones existentes y adapta su acceso a Odoo 19.",
    "license": "LGPL-3",
    "depends": [
        "hr",
        "hr_payroll",
        "hr_holidays",
        "l10n_cl_hr",
        "l10n_cl_hr_payroll_reports",
    ],
    "data": [
        "views/hr_payslip_run_views.xml",
        "views/hr_employee_views.xml",
        "report/certificate_templates.xml",
        "report/payroll_footer_templates.xml",
    ],
    "installable": True,
    "application": False,
}
