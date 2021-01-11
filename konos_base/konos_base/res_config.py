# -*- coding: utf-8 -*-
from odoo import models, fields
from odoo.tools.translate import _


class konos_base_configuration(models.TransientModel):
    '''Inherit Odoo base config'''
    _name = 'konos.base.config.settings'
    _inherit = 'res.config.settings'



    module_l10n_cl_fe = fields.Boolean(
        'Electronic Invoice Chile',
        help="""Installs module module_l10n_cl_fe, and all Electronic Invoice requirements.""")


    module_l10n_cl_dte_factoring = fields.Boolean(
        'DTE Factoring',
        help="""Installs module l10n_cl_dte_factoring, and all DTE requirements.""")

    module_l10n_cl_stock_picking = fields.Boolean(
        'DTE Guías de Despacho Electrónicas',
        help="""Installs module l10n_cl_stock_picking, and all DTE requirements.""")


    module_l10n_cl_dte_point_of_sale = fields.Boolean(
        'DTE Punto de Venta',
        help="""Installs module 10n_cl_dte_point_of_sale, and all DTE requirements.""")


    module_l10n_cl_banks_sbif = fields.Boolean(
        'Bancos en Chile',
        help="""Installs module l10n_cl_banks_sbif, and includes authorized
banks, and financial institutions in Chile.""")

    module_l10n_cl_chart_of_account = fields.Boolean(
        'Plan de Cuentas SII',
        help="""Installs module l10n_cl_chart_of_account, and includes authorized
chart of accounts in Chile.""")


    module_l10n_cl_financial_indicators = fields.Boolean(
        'Indicadores Financieros',
        help="""Installs module l10n_cl_financial_indicators, allowing to
update indicators daily, from SBIF.""")

    module_l10n_cl_hr = fields.Boolean(
        'Liquidaciones en Chile',
        help="""Install l10n_cl_hr for payroll and AFPs chilean
modules""")


    module_currency_rate_inverted = fields.Boolean(
        'Currency Rate Inverted',
        help="""Installs currency_rate_inverted.""")

    module_mass_editing = fields.Boolean(
        'Edición Masiva',
        help="""Installs module_mass_editing.""")

    module_account_cancel = fields.Boolean(
        'Account Cancel',
        help="""Installs module_account_cancel.""")

    module_web_export_view = fields.Boolean(
        'Excel Export',
        help="""Installs module_web_export_view.""")
    
    module_account_payment_group = fields.Boolean(
        'Payment Group',
        help="""Installs module_account_payment_group.""")

    module_vit_journal_voucher = fields.Boolean(
        'Impresión de Comprobantes Contables',
        help="""Installs vit_journal_voucher.""")

    module_l10n_cl_balance = fields.Boolean(
        'Reportes Contables en Chile',
        help="""Installs module_l10n_cl_balance.""")

    module_layouts_custom = fields.Boolean(
        'Layouts Custom',
        help="""Installs module_layouts_custom.""")

    module_customer_account_followup = fields.Boolean(
        'Seguimiento de Cheques y Pagos',
        help="""Installs module_customer_account_followup.""")

    module_payroll_analytic_account = fields.Boolean(
        'Centros de Costos en Liquidaciones',
        help="""Installs module_payroll_analytic_account.""")

    module_payroll_cancel = fields.Boolean(
        'Cancelar Nómina',
        help="""Installs module_payroll_cancel.""")

    module_auth_signup = fields.Boolean(
        'Auth Signup',
        help="""Installs module_auth_signup.""")

    module_auto_backup = fields.Boolean(
        'Auto Backup',
        help="""Installs module_auto_backup.""")

    module_document = fields.Boolean(
        'Documentos Adjuntos',
        help="""Installs module_document.""")
    
    module_account_financial_report = fields.Boolean(
        'Reportes Financieros OCA',
        help="""Installs module_account_financial_report.""")


    module_cl_import_bank_statement_line = fields.Boolean(
        'Cartola Bancaria - Importación de Cartolas Chile',
        help="""Installs module_cl_import_bank_statement_line.""")

    module_contacts = fields.Boolean(
        'Contactos',
        help="""Installs module_contacts.""")

    module_report = fields.Boolean(
        'Reportes',
        help="""Installs module_report.""")

    module_board = fields.Boolean(
        'Dashboard',
        help="""Installs module_board.""")

    module_account_payment_advance = fields.Boolean(
        'Account Payment Advance',
        help="""Installs module_account_payment_advance.""")




    
