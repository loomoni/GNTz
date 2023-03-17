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
    delivery_attachment = fields.Binary(string="Delivery Attachment", attachment=True, store=True, )
    delivery_attachment_name = fields.Char('Delivery Attachment Name')
    delivery_note_no = fields.Char('Delivery Note No', required=False)
    goods_received_date = fields.Date(string="Goods Received Date", required=True, default=fields.Date.today())
    receiver_id = fields.Many2one('hr.employee', string="Received By", required=True, default=_default_receiver)
    department_id = fields.Char(string='Department', compute="department_compute")
    project_id = fields.Char(string='Department', compute="project_compute")
    supplier_id = fields.Many2one('res.partner', string="Supplier", domain=[('supplier', '=', True)])
    purchaser_id = fields.Many2one('hr.employee', string="Purchased By")
    invoice_no = fields.Many2one('account.invoice', string="Invoice No")
    state = fields.Selection(STATE_SELECTION, index=True, track_visibility='onchange',
                             readonly=True, required=True, copy=False, default='draft', store=True)
    line_ids = fields.One2many('inventory.stockin.lines', 'stockin_id', string="Stock In Lines", index=True,
                               track_visibility='onchange')

    @api.onchange('line_ids.department_name')
    @api.depends('line_ids.department_name')
    def department_compute(self):
        for rec in self:
            rec.department_id = rec.line_ids.department_name

    @api.onchange('line_ids.project_name')
    @api.depends('line_ids.project_name')
    def project_compute(self):
        for rec in self:
            rec.project_id = rec.line_ids.project_name

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
    department = fields.Many2one(comodel_name='hr.department', string='Department')
    department_name = fields.Char(string='Department', related='department.name')
    project = fields.Many2one(comodel_name='project.configuration', string='Project')
    project_name = fields.Char(string='Project Name', related='project.name')
    cost = fields.Float('Total Cost', digits=(12, 2), required=True, default=1)
    received_date = fields.Date('Received Date', compute="compute_date")
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure',
                             default=lambda self: self.env['uom.uom'].search([], limit=1, order='id'))
    stockin_id = fields.Many2one('inventory.stockin', string="Stock In")
    state = fields.Selection(STATE_SELECTION, index=True, track_visibility='onchange', related='stockin_id.state',
                             store=True)

    @api.depends('stockin_id.goods_received_date')
    def compute_date(self):
        for rec in self:
            rec.received_date = rec.stockin_id.goods_received_date


class InventoryStockOut(models.Model):
    _name = "inventory.stockout"
    _description = "Stock Out"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id'

    STATE_SELECTION = [
        ("draft", "Draft"),
        ("requested", "Requested"),
        ("line_manager", "Line Manager Reviewed"),
        ("checked", "Procurement Checked"),
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
    def button_line_manager(self):
        self.write({'state': 'line_manager'})
        return True

    @api.multi
    def button_checked(self):
        for line in self.line_ids:
            if line.issued_quantity <= 0:
                raise ValidationError(_("You can't issue 0 goods"))
        self.write({'state': 'checked'})
        for line in self.line_ids:
            line.product_id._amount_quantity()
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
    department = fields.Many2one(comodel_name='hr.department', string='Department')
    request_reason = fields.Text(string='Purpose', required=True)
    project = fields.Many2one(comodel_name='project.configuration', string='Project', required=True)
    requested_quantity = fields.Float('Requested Quantity', digits=(12, 2), required=True, default=1)
    issued_quantity = fields.Float('Issued Quantity', digits=(12, 2))
    requested_date = fields.Date(string='Requested Date', compute="requested_date_compute")
    balance_stock = fields.Float('Balance Stock', digits=(12, 2), required=True)
    balance_stock_department = fields.Float('Balance Department', digits=(12, 2), required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure',
                             default=lambda self: self.env['uom.uom'].search([], limit=1, order='id'))
    stockout_id = fields.Many2one('inventory.stockout', string="Stock Out")
    state = fields.Selection(STATE_SELECTION, index=True, track_visibility='onchange', related='stockout_id.state',
                             store=True)

    @api.depends('stockout_id.request_date')
    def requested_date_compute(self):
        for rec in self:
            rec.requested_date = rec.stockout_id.request_date

    @api.onchange('product_id')
    @api.depends('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.balance_stock = self.product_id.balance_stock

    @api.onchange('department', 'product_id')
    @api.depends('department', 'product_id')
    def onchange_department(self):
        if self.department:
            self

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
    adjustment_quantity = fields.Float('Adjusted Quantity', digits=(12, 2), store=True, compute='_amount_quantity')
    balance_stock = fields.Float('Balance Stock', digits=(12, 2), store=True, compute='_amount_quantity')
    stockin_ids = fields.One2many('inventory.stockin.lines', 'product_id', string="Stock In Lines", index=True,
                                  track_visibility='onchange', store=True)
    department_id = fields.Many2one(comodel_name='hr.department', string="Department", required=True)
    stockout_ids = fields.One2many('inventory.stockout.lines', 'product_id', string="Stock Out Lines", index=True,
                                   track_visibility='onchange', store=True)
    stock_adjustment_ids = fields.One2many('inventory.stock.adjustment.line', 'product_id',
                                           string="Inventory Adjustment", index=True,
                                           track_visibility='onchange', store=True)
    qty_available = fields.Float('On hand', digits=(12, 2), store=True, compute='_amount_quantity')
    virtual_available = fields.Float('Forecasted', digits=(12, 2), store=True, compute='_amount_quantity')

    @api.depends('stockin_ids.quantity', 'stockout_ids.issued_quantity', 'stock_adjustment_ids.adjustment')
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
            adjustement = 0
            for line in record.stock_adjustment_ids:
                if line.product_line_id.state == "approved":
                    adjustement += line.adjustment
            record.purchased_quantity = stockins
            record.issued_quantity = stockouts
            record.adjustment_quantity = adjustement
            record.balance_stock = stockins - stockouts - adjustement
            record.qty_available = record.balance_stock
            record.virtual_available = record.qty_available


class InventoryProductStockAdjustment(models.Model):
    _name = "inventory.stock.adjustment"
    _description = "Stock Inventory Adjustment"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    STATE_SELECTION = [
        ("draft", "Draft"),
        ("submit", "Submitted"),
        ("line_manager", "Line Manager Reviewed"),
        ("verify", "Procurement Verified"),
        ("approved", "Approved"),
        ("rejected", "Rejected")
    ]

    @api.multi
    def button_submit(self):
        for line in self.stock_adjustment_line_ids:
            if line.adjustment <= 0:
                raise ValidationError(_("You should specify adjusted value amount"))
            line.state = "submit"
        self.write({'state': 'submit'})
        return True

    @api.multi
    def button_line_manager(self):
        for line in self.stock_adjustment_line_ids:
            line.state = "line_manager"
        self.write({'state': 'line_manager'})
        return True

    @api.multi
    def button_verify(self):
        self.write({'state': 'approved'})
        for line in self.stock_adjustment_line_ids:
            line.state = "approved"
        for line in self.stock_adjustment_line_ids:
            line.product_id._amount_quantity()
        return True

    @api.multi
    def button_review(self):
        for line in self.stock_adjustment_line_ids:
            line.state = "draft"
        self.write({'state': 'draft'})
        return True

    @api.multi
    def button_approve(self):
        for line in self.stock_adjustment_line_ids:
            line.state = "approved"
        self.write({'state': 'approved'})
        return True

    @api.multi
    def button_reject(self):
        for line in self.stock_adjustment_line_ids:
            line.state = "rejected"
        self.write({'state': 'rejected'})
        return True

    name = fields.Char(string='Inventory Reference', required=True)
    attachment = fields.Binary(string="Attachment", attachment=True, store=True, )
    attachment_name = fields.Char('Attachment Name')
    date = fields.Date(string='Date')
    employee = fields.Many2one(comodel_name='hr.employee', string='Employee')
    state = fields.Selection(STATE_SELECTION, index=True, track_visibility='onchange',
                             readonly=True, required=True, copy=False, default='draft', store=True)
    stock_adjustment_line_ids = fields.One2many('inventory.stock.adjustment.line', 'product_line_id',
                                                string="Stock Adjustment Lines")


class InventoryProductStockAdjustmentLines(models.Model):
    _name = "inventory.stock.adjustment.line"
    _description = "Stock Adjustment Lines"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    STATE_SELECTION = [
        ("draft", "Draft"),
        ("submit", "Submitted"),
        ("line_manager", "Line Manager Reviewed"),
        ("verify", "Procurement Verified"),
        ("approved", "Approved"),
        ("rejected", "Rejected")
    ]

    state = fields.Selection(STATE_SELECTION, index=True, track_visibility='onchange',
                             readonly=True, required=True, copy=False, default='draft', store=True)
    product_id = fields.Many2one(comodel_name="product.template", string="Product")
    Actual_value = fields.Float(string="Available", related='product_id.balance_stock')
    adjustment = fields.Float(string="Adjustment")
    reason = fields.Text(string="Adjustment Reason")
    adjustment_date = fields.Date(string="Adjustment Date", compute="adjustment_data")
    product_line_id = fields.Many2one(comodel_name='inventory.stock.adjustment', string="Stock Adjustment",
                                      required=False)

    @api.depends('product_line_id.date')
    def adjustment_data(self):
        for rec in self:
            rec.adjustment_date = rec.product_line_id.date


class ProjectConfiguration(models.Model):
    _name = "project.configuration"
    _description = "Projects Configurations"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Project Name")
    location = fields.Char(string="Project Location")
