# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LandedCost(models.Model):
    _inherit = 'stock.landed.cost'

    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        help='Analytic account used to find vendor bill lines that generate landed cost lines.',
    )

    def search_analytic_account(self):
        self.ensure_one()

        if self.cost_lines:
            raise ValidationError(_('The cost lines were already generated.'))
        if not self.analytic_account_id:
            raise ValidationError(_('Select an analytic account first.'))

        invoice_lines = self.env['account.move.line'].search([
            ('move_id.state', '!=', 'cancel'),
            ('move_id.move_type', 'in', ('in_invoice', 'in_refund')),
            ('analytic_distribution', 'in', self.analytic_account_id.ids),
        ])

        cost_lines = {}
        for invoice_line in invoice_lines.filtered(lambda line: line.product_id.landed_cost_ok):
            cost_lines[invoice_line.product_id] = (
                cost_lines.get(invoice_line.product_id, 0.0) + invoice_line.price_subtotal
            )

        if not cost_lines:
            raise ValidationError(_('No landed cost product was found for this analytic account.'))

        self.write({
            'cost_lines': [(0, 0, {
                'product_id': product.id,
                'name': product.name or '',
                'split_method': product.product_tmpl_id.split_method_landed_cost or 'equal',
                'price_unit': price,
                'account_id': product.product_tmpl_id.get_product_accounts()['expense'].id,
            }) for product, price in cost_lines.items()],
        })


class AdjustmentLines(models.Model):
    _inherit = 'stock.valuation.adjustment.lines'

    new_cost = fields.Float(
        compute='_compute_new_cost',
        help='New Value / Quantity',
    )

    @api.depends('final_cost', 'quantity')
    def _compute_new_cost(self):
        for record in self:
            record.new_cost = record.quantity and record.final_cost / record.quantity or 0.0
