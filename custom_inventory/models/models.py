# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime
from dateutil.relativedelta import relativedelta
import math
from odoo.exceptions import ValidationError, UserError


class InventoryStockIn(models.Model):
    _name = "inventory.stockin"
    _description = "Stock In"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id'

    STATE_SELECTION = [
        ("draft", "Draft"),
        ("submit", "Submitted"),
        ("procurement", "Procurement Review"),
        ("approved", "Delivery Approved"),
        ("rejected", "Rejected")
    ]

    def _default_reference(self):
        inventoryList = self.env['inventory.stockin'].sudo().search_count([])
        return 'INVENTORY/STOCKIN/00' + str(inventoryList + 1)

    def _default_receiver(self):
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        if employee:
            return employee.id

    name = fields.Char('Serial No', required=True, default=_default_reference)
    delivery_note_no = fields.Char('Delivery Note No', required=True)
    goods_received_date = fields.Date(string="Goods Received Date", required=True, default=fields.Date.today())
    receiver_id = fields.Many2one('hr.employee', string="Received By", required=True, default=_default_receiver)
    department_id = fields.Many2one('hr.department', string='Department', required=True)
    supplier_id = fields.Many2one('res.partner', string="Supplier", domain=[('supplier', '=', True)])
    purchaser_id = fields.Many2one('hr.employee', string="Purchased By")
    invoice_no = fields.Many2one('account.invoice', string="Invoice No")
    state = fields.Selection(STATE_SELECTION, index=True, track_visibility='onchange',
                             readonly=True, required=True, copy=False, default='draft', store=True)
    line_ids = fields.One2many('inventory.stockin.lines', 'stockin_id', string="Stock In Lines", index=True,
                               track_visibility='onchange')

    @api.multi
    def button_approve(self):
        self.write({'state': 'approved'})
        for line in self.line_ids:
            line.product_id._amount_quantity()
        return True

    @api.multi
    def button_reject(self):
        self.write({'state': 'rejected'})
        return True

    @api.multi
    def button_submit(self):
        self.write({'state': 'submit'})
        return True

    @api.multi
    def button_procurement(self):
        self.write({'state': 'procurement'})
        return True

    @api.multi
    def button_reset(self):
        self.write({'state': 'draft'})
        return True


class InventoryStockInLines(models.Model):
    _name = "inventory.stockin.lines"
    _description = "Stock In Lines"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    STATE_SELECTION = [
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("rejected", "Rejected")
    ]

    product_id = fields.Many2one('product.template', string="Product", required=True)
    quantity = fields.Float('Quantity', digits=(12, 2), required=True, default=1)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure',
                             default=lambda self: self.env['uom.uom'].search([], limit=1, order='id'))
    stockin_id = fields.Many2one('inventory.stockin', string="Stock In")
    state = fields.Selection(STATE_SELECTION, index=True, track_visibility='onchange', related='stockin_id.state',
                             store=True)


class InventoryStockOut(models.Model):
    _name = "inventory.stockout"
    _description = "Stock Out"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id'

    STATE_SELECTION = [
        ("draft", "Draft"),
        ("requested", "Requested"),
        ("checked", "Procurement Checked"),
        # ("approved", "Approved StockOut"),
        ("issued", "Issued Out"),
        ("rejected", "Rejected")
    ]

    def _default_reference(self):
        inventoryList = self.env['inventory.stockout'].sudo().search_count([])
        return 'INVENTORY/STOCKOUT/00' + str(inventoryList + 1)

    def _default_requester(self):
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        if employee:
            return employee.id

    def _default_department(self):
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        if employee and employee.department_id:
            return employee.department_id.id

    name = fields.Char('Serial No', required=True, default=_default_reference)
    # outlet_name = fields.Char('Outlet Name', required=True)
    request_date = fields.Date(string="Request Date", required=True, default=fields.Date.today())
    requester_id = fields.Many2one('hr.employee', string="Requested By", required=True, default=_default_requester,
                                   readonly=True, store=True, states={'draft': [('readonly', False)]})
    issuer_id = fields.Many2one('hr.employee', string="Issued By", required=True)
    department_id = fields.Many2one('hr.department', string='Department', required=True, default=_default_department,
                                    readonly=True, store=True, states={'draft': [('readonly', False)]})
    state = fields.Selection(STATE_SELECTION, index=True, track_visibility='onchange',
                             readonly=True, required=True, copy=False, default='draft', store=True)
    line_ids = fields.One2many('inventory.stockout.lines', 'stockout_id', string="Stock Out Lines", index=True,
                               track_visibility='onchange')

    @api.multi
    def button_requested(self):
        self.write({'state': 'requested'})
        return True

    @api.multi
    def button_checked(self):
        self.write({'state': 'checked'})
        return True

    @api.multi
    def button_approve(self):
        self.write({'state': 'approved'})
        return True

    @api.multi
    def button_issue(self):
        for line in self.line_ids:
            if line.issued_quantity <= 0:
                raise ValidationError(_("One of The Lines Has an Invalid Issued Amount.Please Check"))
        self.write({'state': 'issued'})
        for line in self.line_ids:
            line.product_id._amount_quantity()
        return True

    @api.multi
    def button_reject(self):
        self.write({'state': 'rejected'})
        return True

    @api.multi
    def button_reset(self):
        self.write({'state': 'draft'})
        return True


class InventoryStockOutLines(models.Model):
    _name = "inventory.stockout.lines"
    _description = "Stock Out Lines"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    STATE_SELECTION = [
        ("draft", "Requested"),
        ("checked", "Checked By SS"),
        ("approved", "Approved By Branch Manager"),
        ("issued", "Issued By Store Keeper"),
        ("rejected", "Rejected")
    ]

    product_id = fields.Many2one('product.template', string="Product", required=True)
    requested_quantity = fields.Float('Requested Quantity', digits=(12, 2), required=True, default=1)
    issued_quantity = fields.Float('Issued Quantity', digits=(12, 2))
    balance_stock = fields.Float('Balance Stock', digits=(12, 2), required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure',
                             default=lambda self: self.env['uom.uom'].search([], limit=1, order='id'))
    stockout_id = fields.Many2one('inventory.stockout', string="Stock Out")
    state = fields.Selection(STATE_SELECTION, index=True, track_visibility='onchange', related='stockout_id.state',
                             store=True)

    @api.onchange('product_id')
    @api.depends('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.balance_stock = self.product_id.balance_stock

    @api.onchange('requested_quantity')
    @api.depends('requested_quantity')
    def onchange_requested_quantity(self):
        if self.requested_quantity and self.balance_stock:
            if self.balance_stock < self.requested_quantity:
                raise ValidationError(_("Please Enter a Value <= Balance Stock"))

    @api.constrains('balance_stock', 'requested_quantity', 'issued_quantity')
    def _issued_and_requested_quantities(self):
        for record in self:
            if record.balance_stock < record.requested_quantity:
                raise ValidationError(
                    _("Please Enter a Value <= Balance Stock"))
            if record.issued_quantity > record.requested_quantity:
                raise ValidationError(
                    _("Please Enter a Value <= Requested Quantity"))


class InventoryStockAdjustment(models.Model):
    _inherit = "stock.inventory"

    accounting_date = fields.Date(string='Accounting Date')


class InventoryProductStock(models.Model):
    _inherit = "product.template"

    purchased_quantity = fields.Float('Purchased Quantity', digits=(12, 2), store=True, compute='_amount_quantity')
    issued_quantity = fields.Float('Issued Quantity', digits=(12, 2), store=True, compute='_amount_quantity')
    balance_stock = fields.Float('Balance Stock', digits=(12, 2), store=True, compute='_amount_quantity')
    stockin_ids = fields.One2many('inventory.stockin.lines', 'product_id', string="Stock In Lines", index=True,
                                  track_visibility='onchange', store=True)
    department_id = fields.Many2one(comodel_name='hr.department', string="Department", required=True)
    stockout_ids = fields.One2many('inventory.stockout.lines', 'product_id', string="Stock Out Lines", index=True,
                                   track_visibility='onchange', store=True)
    qty_available = fields.Float('On hand', digits=(12, 2), store=True, compute='_amount_quantity')
    virtual_available = fields.Float('Forecasted', digits=(12, 2), store=True, compute='_amount_quantity')

    @api.depends('stockin_ids.quantity', 'stockout_ids.issued_quantity')
    def _amount_quantity(self):
        for record in self:
            stockins = 0
            for line in record.stockin_ids:
                if line.stockin_id.state == "approved":
                    stockins += line.quantity
            stockouts = 0
            for line in record.stockout_ids:
                if line.stockout_id.state == "issued":
                    stockouts += line.issued_quantity
            record.purchased_quantity = stockins
            record.issued_quantity = stockouts
            record.balance_stock = stockins - stockouts
            record.qty_available = record.balance_stock
            record.virtual_available = record.qty_available
        #     record.balance_stock = 2
