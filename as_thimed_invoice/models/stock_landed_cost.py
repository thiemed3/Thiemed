# -*- coding: utf-8 -*-
from collections import defaultdict
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_is_zero

class LandedCost(models.Model):
    _inherit = 'stock.landed.cost'

    analytic_tag_id = fields.Many2one(
        'account.analytic.tag', string="Analytic tag",
        help="Analytic tag associated with the invoice. E.g. DIN1")

    @api.depends('cost_lines.price_unit')
    def _compute_total_amount(self):
        for cost in self:
            prec_digits = self.env.company.currency_id.decimal_places
            cost.amount_total = sum(round(line.price_unit,prec_digits) for line in cost.cost_lines)

    def compute_landed_cost(self):
        AdjustementLines = self.env['stock.valuation.adjustment.lines']
        AdjustementLines.search([('cost_id', 'in', self.ids)]).unlink()

        digits = self.env['decimal.precision'].precision_get('Product Price')
        towrite_dict = {}
        for cost in self.filtered(lambda cost: cost._get_targeted_move_ids()):
            total_qty = 0.0
            total_cost = 0.0
            total_weight = 0.0
            total_volume = 0.0
            total_line = 0.0
            all_val_line_values = cost.get_valuation_lines()
            for val_line_values in all_val_line_values:
                for cost_line in cost.cost_lines:
                    val_line_values.update({'cost_id': cost.id, 'cost_line_id': cost_line.id})
                    self.env['stock.valuation.adjustment.lines'].create(val_line_values)
                total_qty += val_line_values.get('quantity', 0.0)
                total_weight += val_line_values.get('weight', 0.0)
                total_volume += val_line_values.get('volume', 0.0)

                former_cost = val_line_values.get('former_cost', 0.0)
                # round this because former_cost on the valuation lines is also rounded
                total_cost += tools.float_round(former_cost, precision_digits=0) if digits else former_cost

                total_line += 1

            for line in cost.cost_lines:
                value_split = 0.0
                for valuation in cost.valuation_adjustment_lines:
                    value = 0.0
                    if valuation.cost_line_id and valuation.cost_line_id.id == line.id:
                        if line.split_method == 'by_quantity' and total_qty:
                            per_unit = (round(line.price_unit) / total_qty)
                            value = valuation.quantity * per_unit
                        elif line.split_method == 'by_weight' and total_weight:
                            per_unit = (round(line.price_unit) / total_weight)
                            value = valuation.weight * per_unit
                        elif line.split_method == 'by_volume' and total_volume:
                            per_unit = (round(line.price_unit) / total_volume)
                            value = valuation.volume * per_unit
                        elif line.split_method == 'equal':
                            value = (round(line.price_unit) / total_line)
                        elif line.split_method == 'by_current_cost_price' and total_cost:
                            per_unit = (round(line.price_unit) / total_cost)
                            value = valuation.former_cost * per_unit
                        else:
                            value = (round(line.price_unit) / total_line)

                        if digits:
                            value = tools.float_round(value, precision_digits=0, rounding_method='UP')
                            fnc = min if line.price_unit > 0 else max
                            value = fnc(value, line.price_unit - value_split)
                            value_split += value

                        if valuation.id not in towrite_dict:
                            towrite_dict[valuation.id] = value
                        else:
                            towrite_dict[valuation.id] += value
        for key, value in towrite_dict.items():
            AdjustementLines.browse(key).write({'additional_landed_cost': (value)})
        return True

    def _check_sum(self):
        """ Check if each cost line its valuation lines sum to the correct amount
        and if the overall total amount is correct also """
        prec_digits = self.env.company.currency_id.decimal_places
        for landed_cost in self:
            total_amount = sum(landed_cost.valuation_adjustment_lines.mapped('additional_landed_cost'))
            if not tools.float_is_zero(total_amount - landed_cost.amount_total, precision_digits=prec_digits):
                return False

            val_to_cost_lines = defaultdict(lambda: 0.0)
            for val_line in landed_cost.valuation_adjustment_lines:
                val_to_cost_lines[val_line.cost_line_id] += val_line.additional_landed_cost
            if any(not tools.float_is_zero(round(cost_line.price_unit,) - val_amount, precision_digits=prec_digits)
                   for cost_line, val_amount in val_to_cost_lines.items()):
                return False
        return True

    def search_tags(self):
        
        if self.cost_lines:
            raise ValidationError(_("The cost lines were already generated."))

        invoices = self.env['account.move'].search([]).filtered(
            lambda r: self.analytic_tag_id in r.analytic_tag_ids)

        if not invoices:
            raise ValidationError(_(
                "There are no results for this analytic tag."))

        cost_lines = {}
        for invoice_line in invoices.mapped('invoice_line_ids'):
            if invoice_line.product_id.landed_cost_ok:
                cost_lines.update({
                    invoice_line.product_id: cost_lines.get(
                        invoice_line.product_id, 0.0) + invoice_line.price_unit,
                })

        if not cost_lines:
            raise ValidationError(_(
                "No landed cost product was found for this analytic tag."))

        self.write({
            'cost_lines': [(0, 0, {
                'product_id': product.id,
                'name': product.name or '',
                'split_method': product.split_method_landed_cost or 'equal',
                'price_unit': price,
                'account_id': product.property_account_expense_id.id or product.categ_id.property_account_expense_categ_id.id,
                }) for product, price in cost_lines.items()],
        })


    def get_valuation_lines(self):
        """Overwrites the original method to include average in the validation
        of the cost methods."""
        lines = []

        for move in self.mapped('picking_ids').mapped('move_lines'):
            if move.product_id.valuation != 'real_time' or move.product_id.cost_method not in ['fifo', 'average']:
                continue
            vals = {
                'product_id': move.product_id.id,
                'move_id': move.id,
                'quantity': move.product_qty,
                'former_cost': move.product_id.standard_price,
                'weight': move.product_id.weight * move.product_qty,
                'volume': move.product_id.volume * move.product_qty
            }
            lines.append(vals)

        if not lines and self.mapped('picking_ids'):
            raise UserError(_(
                'The selected picking does not contain any move that would be '
                'impacted by landed costs. Landed costs are only possible for '
                'products configured in real time valuation with real price '
                'costing method. Please make sure it is the case, or you '
                'selected the correct picking'))
        return lines


class AdjustmentLines(models.Model):
    _inherit = 'stock.valuation.adjustment.lines'

    new_cost = fields.Float(
        compute='_compute_new_cost',
        help="Former Cost (Per unit) + Additional Landed Cost / Quantity")

    def _compute_new_cost(self):
        """Computes the new cost amount"""
        for record in self:
            record.new_cost = (
                record.final_cost + record.additional_landed_cost
                / record.quantity)
