# -*- coding: utf-8 -*-
# © 2019 Odoo Latam
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Account Payment with Multiple methods with Massive Unlink",
    "version": "11.0.1.0.0",
    "category": "Accounting",
    "website": "https://www.odoolata.com",
    "author": "Odoo Latam, ADHOC SA, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "application": True,
    'installable': True,
    "depends": [
        "account_payment_group",
        #"account_payment_fix",  # for fixes related to domains on payments
        # "account",
    ],
    "data": [
        # 'views/account_move_line_view.xml',
    ],
    "demo": [
    ],
}
