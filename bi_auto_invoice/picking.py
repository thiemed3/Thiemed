# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.


from datetime import datetime

from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare
from odoo.exceptions import UserError


class StockImmediateTransfer(models.TransientModel):
    _inherit = 'stock.immediate.transfer'


    def process(self):
        pick_to_backorder = self.env['stock.picking']
        pick_to_do = self.env['stock.picking']
        for picking in self.pick_ids:
            # If still in draft => confirm and assign
            if picking.state == 'draft':
                picking.action_confirm()
                if picking.state != 'assigned':
                    picking.action_assign()
                    if picking.state != 'assigned':
                        raise UserError(_("Could not reserve all requested products. Please use the \'Mark as Todo\' button to handle the reservation manually."))
            for move in picking.move_lines:
                if move.move_line_ids:
                    for move_line in move.move_line_ids:
                        move_line.qty_done = move_line.product_uom_qty
                else:
                    move.quantity_done = move.product_uom_qty
            if picking._check_backorder():
                pick_to_backorder |= picking
                continue
            pick_to_do |= picking

        # Process every picking that do not require a backorder, then return a single backorder wizard for every other ones.
        if pick_to_do:
            pick_to_do.action_done()
        if pick_to_backorder:
            return pick_to_backorder.action_generate_backorder_wizard()

class account_invoice(models.Model):

    _inherit  =  'account.invoice'



    picking_id = fields.Many2one('stock.picking','Picking')
    sale_id  =  fields.Many2one('sale.order', 'Sale Origin')
    pur_id   =  fields.Many2one('purchase.order', 'Purchase Origin')
    sale_count = fields.Float('Sales Count')

    @api.onchange('purchase_id')
    def purchase_order_change(self):
        if not self.purchase_id:
            return {}
        if not self.partner_id:
            self.partner_id = self.purchase_id.partner_id.id

        new_lines = self.env['account.invoice.line']
        for line in self.purchase_id.order_line:
            # Load a PO line only once
            if line in self.invoice_line_ids.mapped('purchase_line_id') and line.product_qty <=0:
                continue
            data = self._prepare_invoice_line_from_po_line(line)
            new_line = new_lines.new(data)
            new_line._set_additional_fields(self)
            new_lines += new_line

        self.invoice_line_ids += new_lines
        self.purchase_id = False

        return {}

class stock_picking(models.Model):
    _inherit = 'stock.picking'

    # @api.multi
    def action_done(self):
        """Changes picking state to done by processing the Stock Moves of the Picking

        Normally that happens when the button "Done" is pressed on a Picking view.
        @return: True
        """
        # TDE FIXME: remove decorator when migration the remaining
        # TDE FIXME: draft -> automatically done, if waiting ?? CLEAR ME
        todo_moves = self.mapped('move_lines').filtered(lambda self: self.state in ['draft', 'partially_available', 'assigned', 'confirmed'])
        # Check if there are ops not linked to moves yet
        for pick in self:
            # # Explode manually added packages
            # for ops in pick.move_line_ids.filtered(lambda x: not x.move_id and not x.product_id):
            #     for quant in ops.package_id.quant_ids: #Or use get_content for multiple levels
            #         self.move_line_ids.create({'product_id': quant.product_id.id,
            #                                    'package_id': quant.package_id.id,
            #                                    'result_package_id': ops.result_package_id,
            #                                    'lot_id': quant.lot_id.id,
            #                                    'owner_id': quant.owner_id.id,
            #                                    'product_uom_id': quant.product_id.uom_id.id,
            #                                    'product_qty': quant.qty,
            #                                    'qty_done': quant.qty,
            #                                    'location_id': quant.location_id.id, # Could be ops too
            #                                    'location_dest_id': ops.location_dest_id.id,
            #                                    'picking_id': pick.id
            #                                    }) # Might change first element
            # # Link existing moves or add moves when no one is related
            for ops in pick.move_line_ids.filtered(lambda x: not x.move_id):
                # Search move with this product
                moves = pick.move_lines.filtered(lambda x: x.product_id == ops.product_id)
                if moves: #could search move that needs it the most (that has some quantities left)
                    ops.move_id = moves[0].id
                else:
                    new_move = self.env['stock.move'].create({
                        'name': _('New Move:') + ops.product_id.display_name,
                        'product_id': ops.product_id.id,
                        'product_uom_qty': ops.qty_done,
                        'product_uom': ops.product_uom_id.id,
                        'location_id': pick.location_id.id,
                        'location_dest_id': pick.location_dest_id.id,
                        'picking_id': pick.id,
                    })
                    ops.move_id = new_move.id
                    new_move._action_confirm()
                    todo_moves |= new_move
                    #'qty_done': ops.qty_done})
        todo_moves._action_done()
        self.write({'date_done': fields.Datetime.now()})
        if self.state == 'done':
            if self.picking_type_id.code == 'incoming':
                account_inv_obj = self.env['account.invoice']
                vals  = {'type': 'in_invoice', 'origin':self.origin ,'pur_id':self.purchase_id.id ,'purchase_id': self.purchase_id.id,'partner_id': self.partner_id.id,'picking_id': self.id }

                res = account_inv_obj.create(vals)
                res.purchase_order_change()
                res.compute_taxes()
                res._onchange_partner_id()
                for purchase_line in account_inv_obj.invoice_line_ids:
                    if purchase_line.quantity <= 0:
                        purchase_line.unlink()

            if self.picking_type_id.code == 'outgoing':
                inv_obj = self.env['account.invoice']
                invoice_lines =[]
                sale_order_line_obj = self.env['account.invoice.line']
                sale_order  =  self.env['sale.order'].search([('name', '=',self.origin )])
                if sale_order:
                    invoice = inv_obj.create({
                        'origin': self.origin,
                        'picking_id':self.id,
                        'type': 'out_invoice',
                        'reference': False,
                        'sale_id':sale_order.id,
                        'date_invoice':datetime.today(),
                        'account_id': self.partner_id.property_account_receivable_id.id,
                        'partner_id': self.partner_id.id,
                        'currency_id': sale_order.pricelist_id.currency_id.id,
                        'payment_term_id': sale_order.payment_term_id.id,
                        'fiscal_position_id': sale_order.fiscal_position_id.id or sale_order.partner_id.property_account_position_id.id,
                        'team_id': sale_order.team_id.id,
                        'comment': sale_order.note,})
                    for sale_line in self.move_lines:
                        if sale_line.product_id.property_account_income_id:
                            account = sale_line.product_id.property_account_income_id
                        elif sale_line.product_id.categ_id.property_account_income_categ_id:
                            account = sale_line.product_id.categ_id.property_account_income_categ_id
                        else:
                            account_search = self.env['ir.property'].search([('name', '=', 'property_account_income_categ_id')])
                            account = account_search.value_reference
                            account = account.split(",")[1]
                            account = self.env['account.account'].browse(account)
                        inv_line=sale_order_line_obj.create({               'name': sale_line.name,
                                                                            'account_id': account.id,
                                                                            'invoice_id':invoice.id,
                                                                             'price_unit': sale_line.price_unit *-1,
                                                                            'quantity': sale_line.product_uom_qty,
                                                                            'uom_id': sale_line.product_id.uom_id.id,
                                                                            'product_id': sale_line.product_id.id,
                                                                            })
                        order_line = self.env['sale.order.line'].search([('order_id', '=', sale_order.id),('product_id', '=',sale_line.product_id.id )])
                        for order_line in order_line:
                            order_line.write({'qty_to_invoice':sale_line.product_uom_qty,'invoice_lines':[(4,inv_line.id)]})

                        tax_ids = []
                        if order_line and order_line[0]:
                            for tax in order_line[0].tax_id:
                                tax_ids.append(tax.id)

                                inv_line.write({'price_unit':order_line[0].price_unit, 'discount': order_line[0].discount, 'invoice_line_tax_ids': [(6,0,tax_ids)]   })
                    invoice.compute_taxes()         

        return True

    @api.depends('state')
    # # @api.one
    def _get_invoiced(self):
        for order in self:
            invoice_ids = self.env['account.invoice'].search([('picking_id','=',order.id)])
            order.invoice_count = len(invoice_ids)


    invoice_count = fields.Integer(string='# of Invoices', compute='_get_invoiced',  )

    # @api.multi
    def button_view_invoice(self):
        mod_obj = self.env['ir.model.data']
        act_obj = self.env['ir.actions.act_window']
        work_order_id = self.env['account.invoice'].search([('picking_id', '=', self.id)])
        inv_ids = []

        for inv_id in  work_order_id:
            inv_ids.append(inv_id.id)
            result = mod_obj.get_object_reference('account', 'action_invoice_tree1')
            id = result and result[1] or False
            result = act_obj.browse(id).read()[0]
            res = mod_obj.get_object_reference('account', 'invoice_form')
            result['views'] = [(res and res[1] or False, 'form')]
            result['res_id'] = work_order_id[0].id or False
        return result

    # @api.multi
    def do_transfer(self):
        """ If no pack operation, we do simple action_done of the picking.
        Otherwise, do the pack operations. """
        # TDE CLEAN ME: reclean me, please
        self._create_lots_for_picking()

        no_pack_op_pickings = self.filtered(lambda picking: not picking.pack_operation_ids)
        no_pack_op_pickings.action_done()
        other_pickings = self - no_pack_op_pickings
        for picking in other_pickings:

            need_rereserve, all_op_processed = picking.picking_recompute_remaining_quantities()
            todo_moves = self.env['stock.move']
            toassign_moves = self.env['stock.move']

            # create extra moves in the picking (unexpected product moves coming from pack operations)
            if not all_op_processed:
                todo_moves |= picking._create_extra_moves()

            if need_rereserve or not all_op_processed:
                moves_reassign = any(x.origin_returned_move_id or x.move_orig_ids for x in picking.move_lines if x.state not in ['done', 'cancel'])
                if moves_reassign and picking.location_id.usage not in ("supplier", "production", "inventory"):
                    # unnecessary to assign other quants than those involved with pack operations as they will be unreserved anyways.
                    picking.with_context(reserve_only_ops=True, no_state_change=True).rereserve_quants(move_ids=picking.move_lines.ids)
                picking.do_recompute_remaining_quantities()

            # split move lines if needed
            for move in picking.move_lines:
                rounding = move.product_id.uom_id.rounding
                remaining_qty = move.remaining_qty
                if move.state in ('done', 'cancel'):
                    # ignore stock moves cancelled or already done
                    continue
                elif move.state == 'draft':
                    toassign_moves |= move
                if float_compare(remaining_qty, 0,  precision_rounding=rounding) == 0:
                    if move.state in ('draft', 'assigned', 'confirmed'):
                        todo_moves |= move
                elif float_compare(remaining_qty, 0, precision_rounding=rounding) > 0 and float_compare(remaining_qty, move.product_qty, precision_rounding=rounding) < 0:
                    # TDE FIXME: shoudl probably return a move - check for no track key, by the way
                    new_move_id = move.split(remaining_qty)
                    new_move = self.env['stock.move'].with_context(mail_notrack=True).browse(new_move_id)
                    todo_moves |= move
                    # Assign move as it was assigned before
                    toassign_moves |= new_move

            # TDE FIXME: do_only_split does not seem used anymore
            if todo_moves and not self.env.context.get('do_only_split'):
                todo_moves.action_done()
            elif self.env.context.get('do_only_split'):
                picking = picking.with_context(split=todo_moves.ids)

            picking._create_backorder()

            if picking.state == 'done':
                if picking.picking_type_id.code == 'incoming':
                    account_inv_obj = self.env['account.invoice']
                    vals  = {'type': 'in_invoice', 'origin':picking.origin ,'pur_id':picking.purchase_id.id ,'purchase_id': picking.purchase_id.id,'partner_id': picking.partner_id.id,'picking_id': picking.id }

                    res = account_inv_obj.create(vals)
                    res.purchase_order_change()
                    res._onchange_partner_id()
                    res.compute_taxes()      
                    for purchase_line in account_inv_obj.invoice_line_ids:
                        if purchase_line.quantity <= 0:
                            purchase_line.unlink()

            if picking.picking_type_id.code == 'outgoing':


                inv_obj = self.env['account.invoice']
                invoice_lines =[]
                sale_order_line_obj = self.env['account.invoice.line']
                sale_order  =  self.env['sale.order'].search([('name', '=',picking.origin )])

            if sale_order:
                invoice = inv_obj.create({
                    'origin': picking.origin,
                    'picking_id':picking.id,
                    'type': 'out_invoice',
                    'reference': False,
                    'sale_id':sale_order.id,
                    'date_invoice':datetime.today(),
                    'account_id': picking.partner_id.property_account_receivable_id.id,
                    'partner_id': picking.partner_id.id,
                    'currency_id': sale_order.pricelist_id.currency_id.id,
                    'payment_term_id': sale_order.payment_term_id.id,
                    'fiscal_position_id': sale_order.fiscal_position_id.id or sale_order.partner_id.property_account_position_id.id,
                    'team_id': sale_order.team_id.id,
                    'comment': sale_order.note,})

                for sale_line in picking.move_lines:
                    if sale_line.product_id.property_account_income_id:
                        account = sale_line.product_id.property_account_income_id
                    elif sale_line.product_id.categ_id.property_account_income_categ_id:
                        account = sale_line.product_id.categ_id.property_account_income_categ_id
                    else:
                        account_search = self.env['ir.property'].search([('name', '=', 'property_account_income_categ_id')])
                        account = account_search.value_reference
                        account = account.split(",")[1]
                        account = self.env['account.account'].browse(account)
                    inv_line=sale_order_line_obj.create({'name': sale_line.name,
                                                        'account_id': account.id,
                                                        'invoice_id':invoice.id,
                                                        'price_unit': sale_line.price_unit *-1,
                                                        'quantity': sale_line.product_uom_qty,
                                                        'uom_id': sale_line.product_id.uom_id.id,
                                                        'product_id': sale_line.product_id.id,
                                                                        })
                    order_line = self.env['sale.order.line'].search([('order_id', '=', sale_order.id),('product_id', '=',sale_line.product_id.id )])
                    for order_line in order_line:
                        order_line.write({'qty_to_invoice':sale_line.product_uom_qty,'invoice_lines':[(4,inv_line.id)]})

                        tax_ids = []
                        if order_line and order_line[0]:
                            for tax in order_line[0].tax_id:
                                tax_ids.append(tax.id)

                            inv_line.write({'price_unit':order_line[0].price_unit, 'discount': order_line[0].discount, 'invoice_line_tax_ids': [(6,0,tax_ids)]   })
            invoice.compute_taxes()
        

        return True


