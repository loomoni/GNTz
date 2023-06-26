# -*- coding: utf-8 -*-
import base64
from io import BytesIO
import xlsxwriter

from xlsxwriter import workbook

from odoo import models, fields, api, _
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import math
from odoo.exceptions import ValidationError, UserError


class InventoryStockIn(models.Model):
    _name = "inventory.stockin"
    _description = "Stock In"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

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

    def _default_department(self):
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        if employee and employee.department_id:
            return employee.department_id.id

    name = fields.Char('Serial No', required=True, default=_default_reference)
    delivery_attachment = fields.Binary(string="Delivery Attachment", attachment=True, store=True, )
    delivery_attachment_name = fields.Char('Delivery Attachment Name')
    delivery_note_no = fields.Char('Delivery Note No', required=False)
    department_id = fields.Many2one('hr.department', required=True, default=_default_department,
                                    readonly=True, store=True, states={'draft': [('readonly', False)]})
    goods_received_date = fields.Date(string="Goods Received Date", required=True, default=fields.Date.today())
    receiver_id = fields.Many2one('hr.employee', string="Received By", required=True, default=_default_receiver)
    supplier_id = fields.Many2one('res.partner', string="Supplier", domain=[('supplier', '=', True)])
    purchaser_id = fields.Many2one('hr.employee', string="Purchased By")
    invoice_no = fields.Many2one('account.invoice', string="Invoice No")
    state = fields.Selection(STATE_SELECTION, index=True, track_visibility='onchange',
                             readonly=True, required=True, copy=False, default='draft', store=True)
    line_ids = fields.One2many('inventory.stockin.lines', 'stockin_id', string="Stock In Lines", index=True,
                               track_visibility='onchange')

    lpo_number = fields.Char(String="LPO NO.")
    lpo_attachment = fields.Binary(string="LPO Attachment", attachment=True, store=True, )
    lpo_attachment_name = fields.Char('Attachment Name')

    gin_number = fields.Char(String="GIN  NO.")
    gin_attachment = fields.Binary(string="GIN Attachment", attachment=True, store=True, )
    gin_attachment_name = fields.Char('Attachment Name')

    grn_number = fields.Char(String="GRN NO.")
    grn_attachment = fields.Binary(string="GRN Attachment", attachment=True, store=True, )
    grn_attachment_name = fields.Char('Attachment Name')

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
    # _order = 'id desc'

    STATE_SELECTION = [
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("rejected", "Rejected")
    ]

    @api.onchange('department')
    def _onchange_department_id(self):
        return {'domain': {'product_id': [('department_id', '=', self.department)]}}

    @api.onchange('stockin_id.department_id')
    @api.depends('stockin_id.department_id')
    def department_compute(self):
        for rec in self:
            rec.department = rec.stockin_id.department_id.id

    @api.depends('quantity', 'unit_cost')
    def total_cost_compute(self):
        for rec in self:
            rec.cost = rec.quantity * rec.unit_cost

    product_id = fields.Many2one('product.template', string="Item", required=True)
    quantity = fields.Float('Quantity', digits=(12, 2), required=True, default=1)
    department = fields.Integer(string='Department', compute="department_compute")
    project = fields.Many2one(comodel_name='project.configuration', string='Project')
    unit_cost = fields.Float('Unit Cost', digits=(12, 2), required=True, default=1)
    cost = fields.Float('Total Cost', digits=(12, 2), required=True, compute="total_cost_compute")
    received_date = fields.Date('Received Date', compute="compute_date")
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure',
                             default=lambda self: self.env['uom.uom'].search([], limit=1, order='id'))
    stockin_id = fields.Many2one('inventory.stockin', string="Stock In")
    reference_no = fields.Char(string="Serial No", related="stockin_id.name")
    department_name = fields.Char(string="Department", related="stockin_id.department_id.name")
    department_id = fields.Integer(string="Department", related="stockin_id.department_id.id")
    receiver_id = fields.Char(string="Received by", related="stockin_id.receiver_id.name")
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
    _order = 'id desc'

    STATE_SELECTION = [
        ("draft", "Draft"),
        ("requested", "Requested"),
        ("line_manager", "Line Manager Approve"),
        ("checked", "Procurement Checked"),
        ("issued", "AD Approved"),
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

    name = fields.Char('Serial No', required=True, default=_default_reference, readonly=True)

    request_date = fields.Date(string="Request Date", required=True, default=fields.Date.today(), readonly=True)
    requester_id = fields.Many2one('hr.employee', string="Requested By", required=True, default=_default_requester,
                                   readonly=True, store=True)
    issuer_id = fields.Many2one('hr.employee', string="Issued By", required=False)
    parent_department = fields.Integer(string="Parent Department", required=False,
                                       related='requester_id.department_parent_id.id')
    # readonly=True,
    department_id = fields.Many2one('hr.department', string='Department', required=True, default=_default_department,
                                store=True, )
    state = fields.Selection(STATE_SELECTION, index=True, track_visibility='onchange',
                             readonly=True, required=True, copy=False, default='draft', store=True)
    line_ids = fields.One2many('inventory.stockout.lines', 'stockout_id', string="Stock Out Lines", index=True,
                               track_visibility='onchange')

    @api.multi
    def button_requested(self):
        self.write({'state': 'requested'})
        mail_template = self.env.ref('custom_inventory.stock_out_staff_request_line_manager_notification_email')
        mail_template.send_mail(self.id, force_send=True)
        return True

        # message = "The request is made"
        # return {
        #     'type': 'ir.actions.client',
        #     'notifications': 'notifications',
        #     'params': {
        #         'message': message,
        #         'type': 'success',
        #         'sticky': True,
        #     }
        # }

        # body_template = self.env.ref('mail.message_activity_assigned')
        # for activity in self:
        #     model_description = self.env['ir.model']._get(activity.res_model).display_name
        #     body = body_template.render(
        #         dict(activity=activity, model_description=model_description),
        #         engine='ir.qweb',
        #         minimal_qcontext=True
        #     )
        #     self.env['mail.thread'].message_notify(
        #         partner_ids=activity.user_id.partner_id.ids,
        #         body=body,
        #         subject=_('%s: %s assigned to you') % (activity.res_name, activity.summary or activity.activity_type_id.name),
        #         record_name=activity.res_name,
        #         model_description=model_description,
        #         notif_layout='mail.mail_notification_light'
        #     )

        # message = "The request is made"
        # return {
        #     'type': 'ir.actions.client',
        #     'title': _('Warning'),
        #     'params': {
        #         'message': message,
        #         'type': 'success',
        #         'sticky': True,
        #     }
        # }

    @api.multi
    def button_line_manager(self, object_id):
        self.write({'state': 'line_manager'})
        mail_template = self.env.ref('custom_inventory.stock_out_line_manager_to_procurement_notification_email')
        mail_template.send_mail(self.id, force_send=True)
        return True



    @api.multi
    def button_review(self):
        self.write({'state': 'draft'})
        return True

    @api.multi
    def button_back_to_line(self):
        self.write({'state': 'line_manager'})
        return True

    @api.multi
    @api.onchange('line.balance_stock', 'line.issued_quantity')
    def button_checked(self):
        for line in self.line_ids:
            if line.issued_quantity <= 0:
                raise ValidationError(_("You can't issue 0 goods"))
            elif line.balance_stock - line.issued_quantity < 0:
                raise ValidationError(_("There is no enough Item to issue please check stock balance"))
        self.write({'state': 'checked'})
        for line in self.line_ids:
            line.product_id._amount_quantity()
        mail_template = self.env.ref('custom_inventory.stock_out_procurement_to_ad_notification_email')
        mail_template.send_mail(self.id, force_send=True)
        return True

    @api.multi
    def button_procurement_review(self):
        self.write({'state': 'line_manager'})
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
        mail_template = self.env.ref('custom_inventory.stock_out_AD_to_requester_notification_email')
        mail_template.send_mail(self.id, force_send=True)
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
    # _order = 'id desc'

    STATE_SELECTION = [
        ("draft", "Draft"),
        ("requested", "Requested"),
        ("line_manager", "Line Manager Reviewed"),
        ("checked", "Procurement Checked"),
        ("issued", "Receipt Confirmed"),
        ("rejected", "Rejected")
    ]

    @api.onchange('department')
    def _onchange_department_id(self):
        return {'domain': {'product_id': ['|', ('department_id', '=', self.department),
                                          ('department_id', '=', self.parent_department)]}}

    @api.onchange('stockout_id.department_id')
    @api.depends('stockout_id.department_id')
    def department_stockout_compute(self):
        for rec in self:
            rec.department = rec.stockout_id.department_id.id

    @api.onchange('stockout_id.requester_id.department_parent_id')
    @api.depends('stockout_id.requester_id.department_parent_id')
    def parent_department_compute(self):
        for rec in self:
            rec.parent_department = rec.stockout_id.requester_id.department_parent_id.id

    product_id = fields.Many2one('product.template', string="Product", required=True)
    department = fields.Integer(string='Department', required=True, compute="department_stockout_compute")
    parent_department = fields.Integer(string='Parent Department', compute="parent_department_compute")
    request_reason = fields.Text(string='Purpose', required=True)
    project = fields.Many2one(comodel_name='project.configuration', string='Project', required=True)
    requested_quantity = fields.Float('Requested Quantity', digits=(12, 2), required=True, default=1)
    issued_quantity = fields.Float('Issued Quantity', digits=(12, 2))
    requested_date = fields.Date(string='Requested Date', compute="requested_date_compute")
    requested_by = fields.Char(string='Requested By', compute="requested_by_compute")
    # balance_stock = fields.Float('Balance Stock', digits=(12, 2), readonly=True)
    balance_stock = fields.Float('Balance Stock', related='product_id.balance_stock')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure',
                             default=lambda self: self.env['uom.uom'].search([], limit=1, order='id'))
    stockout_id = fields.Many2one(comodel_name='inventory.stockout', string="Stock Out")
    department_name = fields.Char(string="Department", related="stockout_id.department_id.name")
    department_id = fields.Integer(string="Department", related="stockout_id.department_id.id")
    state = fields.Selection(STATE_SELECTION, index=True, track_visibility='onchange', related='stockout_id.state',
                             store=True)

    @api.depends('stockout_id.request_date')
    def requested_date_compute(self):
        for rec in self:
            rec.requested_date = rec.stockout_id.request_date

    @api.depends('stockout_id.requester_id.name')
    def requested_by_compute(self):
        for rec in self:
            rec.requested_by = rec.stockout_id.requester_id.name

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
            # if record.balance_stock < record.requested_quantity:
            #     raise ValidationError(
            #         _("Please Enter a Value <= Balance Stock now"))
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
    _order = 'id desc'

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
        self.write({'state': 'verify'})
        for line in self.stock_adjustment_line_ids:
            if line.adjustment <= 0:
                raise ValidationError(_("You should specify adjusted value amount"))
            line.state = "verify"

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
        for line in self.stock_adjustment_line_ids:
            line.product_id._amount_quantity()
        self.write({'state': 'approved'})
        mail_template = self.env.ref('custom_inventory.stock_adjustment_email_to_hod')
        mail_template.send_mail(self.id, force_send=True)
        return True

    @api.multi
    def button_reject(self):
        for line in self.stock_adjustment_line_ids:
            line.state = "rejected"
        self.write({'state': 'rejected'})
        return True

    def _default_employee(self):
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        if employee:
            return employee.id

    def _default_reference(self):
        inventoryList = self.env['inventory.stock.adjustment'].sudo().search_count([])
        return 'INVENTORY/ADJUSTMENT/00' + str(inventoryList + 1)

    name = fields.Char(string='Inventory Reference', default=_default_reference, required=True)
    attachment = fields.Binary(string="Attachment", attachment=True, store=True, )
    attachment_name = fields.Char('Attachment Name')
    date = fields.Date(string='Date', required=True)
    employee = fields.Many2one(comodel_name='hr.employee', string='Employee', required=True, default=_default_employee,
                               readonly=True, store=True)
    state = fields.Selection(STATE_SELECTION, index=True, track_visibility='onchange',
                             readonly=True, required=True, copy=False, default='draft', store=True)
    stock_adjustment_line_ids = fields.One2many('inventory.stock.adjustment.line', 'product_line_id',
                                                string="Stock Adjustment Lines")


class InventoryProductStockAdjustmentLines(models.Model):
    _name = "inventory.stock.adjustment.line"
    _description = "Stock Adjustment Lines"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    # _order = 'id desc'

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


class GeneralInventoryListWizard(models.TransientModel):
    _name = 'general.inventory.report.wizard'

    department_id = fields.Many2one('hr.department', string='Department', required=False)
    department_name = fields.Integer(string='Department', related='department_id.id')
    date_from = fields.Date(string='Date From', required=True,
                            default=lambda self: fields.Date.to_string(date.today().replace(day=1)))
    date_to = fields.Date(string='Date To', required=True,
                          default=lambda self: fields.Date.to_string(
                              (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()))
    company = fields.Many2one('res.company', default=lambda self: self.env['res.company']._company_default_get(),
                              string="Company")

    @api.multi
    def get_report(self):
        file_name = _('Inventory report ' + str(self.date_from) + ' - ' + str(self.date_to) + ' report.xlsx')
        fp = BytesIO()

        workbook = xlsxwriter.Workbook(fp)
        heading_format = workbook.add_format({'align': 'center',
                                              'valign': 'vcenter',
                                              'bold': True,
                                              'size': 14,
                                              'fg_color': '#89A130', })
        heading_format.set_border()
        sub2_heading_format = workbook.add_format({'align': 'center',
                                                   'valign': 'vcenter',
                                                   'bold': True, 'size': 14})
        sub2_heading_format.set_border()
        dr_cr_format = workbook.add_format({'align': 'center',
                                            # 'valign': 'vcenter',
                                            'bold': True, 'size': 14})
        dr_cr_format.set_border()
        sub_heading_format = workbook.add_format({'align': 'left',
                                                  # 'valign': 'vcenter',
                                                  'bold': True, 'size': 14})
        sub_heading_format.set_border()
        cell_text_format_n = workbook.add_format({'align': 'center',
                                                  'bold': True, 'size': 9,
                                                  })
        cell_text_format_n.set_border()
        cell_photo_format = workbook.add_format({'align': 'center',

                                                 })
        cell_photo_format.set_border()
        cell_date_text_format = workbook.add_format({'align': 'left',
                                                     'size': 9,
                                                     })
        cell_date_text_format.set_border()

        approve_format = workbook.add_format({'align': 'left',
                                              'bold': False, 'size': 14,
                                              })

        cell_text_format = workbook.add_format({'align': 'left',
                                                'bold': True, 'size': 13,
                                                'fg_color': '#695B55',
                                                'font_color': 'white'
                                                })

        cell_text_format.set_border()
        cell_text_format_new = workbook.add_format({'align': 'left',
                                                    'size': 9,
                                                    'num_format': '#,###0.00',
                                                    })
        cell_text_format_new.set_border()
        cell_number_format = workbook.add_format({'align': 'right',
                                                  'bold': False, 'size': 9,
                                                  'num_format': '#,###0.00'})
        cell_number_format.set_border()
        worksheet = workbook.add_worksheet(
            'Inventory report ' + str(self.date_from) + ' - ' + str(self.date_to) + ' report.xlsx')
        normal_num_bold = workbook.add_format({'bold': True, 'num_format': '#,###0.00', 'size': 9, })
        normal_num_bold.set_border()
        worksheet.set_column('A:J', 20)
        # worksheet.set_default_row(45)

        worksheet.set_row(0, 20)
        worksheet.set_row(1, 20)
        worksheet.set_row(2, 15)
        worksheet.set_row(3, 15)
        worksheet.set_row(4, 15)
        worksheet.set_row(5, 20)
        row = 2
        row_set = row

        if self.date_from and self.date_to:
            date_2 = datetime.strftime(self.date_to, '%d-%m-%Y')
            date_1 = datetime.strftime(self.date_from, '%d-%m-%Y')
            asset_report_month = self.date_from.strftime("%B")
            worksheet.merge_range('A1:E2', 'Inventory Report For %s %s' % (asset_report_month, self.date_from.year),
                                  heading_format)
            worksheet.write('A3:A3', 'Company', cell_text_format_n)
            worksheet.merge_range('B3:C3', '%s' % self.company.name, cell_text_format_n)

            worksheet.write('A4:A4', 'Department', cell_text_format_n)
            if self.department_name:
                worksheet.merge_range('B4:C4', '%s' % self.department_id.name, cell_text_format_n)
            else:
                worksheet.merge_range('B4:C4', "All", cell_text_format_n)

            worksheet.write(row, 3, 'Date From', cell_text_format_n)
            worksheet.write(row, 4, date_1 or '', cell_date_text_format)
            row += 1
            worksheet.write(row, 3, 'Date To', cell_text_format_n)
            worksheet.write(row, 4, date_2 or '', cell_date_text_format)
            row += 2

            worksheet.write(row, 0, 'Item', cell_text_format)
            # worksheet.write(row, 1, 'Remark', cell_text_format)
            worksheet.write(row, 1, 'Total Purchased', cell_text_format)
            worksheet.write(row, 2, 'Total Used', cell_text_format)
            worksheet.write(row, 3, 'Balance', cell_text_format)

            department_general_inventory = self.env['product.template'].sudo().search(
                [('department_id', '=', self.department_name)])
            general_inventory_report = self.env['product.template'].sudo().search([])

            ro = row + 1
            col = 0
            if department_general_inventory:
                for department_inventory in department_general_inventory:
                    item = department_inventory.name
                    total_purchased = department_inventory.purchased_quantity
                    total_used = department_inventory.issued_quantity
                    balance = department_inventory.balance_stock

                    worksheet.write(ro, col, item or '', cell_text_format_new)
                    # worksheet.write(ro, col + 1, '', cell_text_format_new)
                    worksheet.write(ro, col + 1, total_purchased or '', cell_text_format_new)
                    worksheet.write(ro, col + 2, total_used or '', cell_text_format_new)
                    worksheet.write(ro, col + 3, balance or '', cell_text_format_new)
                    ro = ro + 1
            else:
                for all_inventory_available in general_inventory_report:
                    item = all_inventory_available.name
                    total_purchased = all_inventory_available.purchased_quantity
                    total_used = all_inventory_available.issued_quantity
                    balance = all_inventory_available.balance_stock

                    worksheet.write(ro, col, item or '', cell_text_format_new)
                    # worksheet.write(ro, col + 1, '', cell_text_format_new)
                    worksheet.write(ro, col + 1, total_purchased or '', cell_text_format_new)
                    worksheet.write(ro, col + 2, total_used or '', cell_text_format_new)
                    worksheet.write(ro, col + 3, balance or '', cell_text_format_new)
                    ro = ro + 1

        workbook.close()
        file_download = base64.b64encode(fp.getvalue())
        fp.close()

        self = self.with_context(default_name=file_name, default_file_download=file_download)

        return {
            'name': 'Inventory Report Download',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'general.inventory.report.excel',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': self._context,
        }


class GeneralInventoryReportExcel(models.TransientModel):
    _name = 'general.inventory.report.excel'
    _description = "Inventory report excel table"

    name = fields.Char('File Name', size=256, readonly=True)
    file_download = fields.Binary('Download Asset', readonly=True)


class StockInInventoryListWizard(models.TransientModel):
    _name = 'stockin.inventory.report.wizard'

    department_id = fields.Many2one('hr.department', string='Department', required=False)
    department_name = fields.Integer(string='Department', related='department_id.id')
    date_from = fields.Date(string='Date From', required=True,
                            default=lambda self: fields.Date.to_string(date.today().replace(day=1)))
    date_to = fields.Date(string='Date To', required=True,
                          default=lambda self: fields.Date.to_string(
                              (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()))
    company = fields.Many2one('res.company', default=lambda self: self.env['res.company']._company_default_get(),
                              string="Company")

    @api.multi
    def get_report(self):
        file_name = _('Inventory report ' + str(self.date_from) + ' - ' + str(self.date_to) + ' report.xlsx')
        fp = BytesIO()

        workbook = xlsxwriter.Workbook(fp)
        heading_format = workbook.add_format({'align': 'center',
                                              'valign': 'vcenter',
                                              'bold': True,
                                              'size': 14,
                                              'fg_color': '#89A130', })
        heading_format.set_border()
        sub2_heading_format = workbook.add_format({'align': 'center',
                                                   'valign': 'vcenter',
                                                   'bold': True, 'size': 14})
        sub2_heading_format.set_border()
        dr_cr_format = workbook.add_format({'align': 'center',
                                            # 'valign': 'vcenter',
                                            'bold': True, 'size': 14})
        dr_cr_format.set_border()
        sub_heading_format = workbook.add_format({'align': 'left',
                                                  # 'valign': 'vcenter',
                                                  'bold': True, 'size': 14})
        sub_heading_format.set_border()
        cell_text_format_n = workbook.add_format({'align': 'center',
                                                  'bold': True, 'size': 9,
                                                  })
        cell_text_format_n.set_border()
        cell_photo_format = workbook.add_format({'align': 'center',

                                                 })
        cell_photo_format.set_border()
        cell_date_text_format = workbook.add_format({'align': 'left',
                                                     'size': 9,
                                                     })
        cell_date_text_format.set_border()

        approve_format = workbook.add_format({'align': 'left',
                                              'bold': False, 'size': 14,
                                              })

        cell_text_format = workbook.add_format({'align': 'left',
                                                'bold': True, 'size': 13,
                                                'fg_color': '#695B55',
                                                'font_color': 'white'
                                                })

        cell_text_format.set_border()
        cell_text_format_new = workbook.add_format({'align': 'left',
                                                    'size': 9,
                                                    'num_format': '#,###0.00',
                                                    })
        cell_text_format_new.set_border()
        cell_number_format = workbook.add_format({'align': 'right',
                                                  'bold': False, 'size': 9,
                                                  'num_format': '#,###0.00'})
        cell_number_format.set_border()
        worksheet = workbook.add_worksheet(
            'Inventory report ' + str(self.date_from) + ' - ' + str(self.date_to) + ' report.xlsx')
        normal_num_bold = workbook.add_format({'bold': True, 'num_format': '#,###0.00', 'size': 9, })
        normal_num_bold.set_border()
        worksheet.set_column('A:G', 20)
        # worksheet.set_default_row(45)

        worksheet.set_row(0, 20)
        worksheet.set_row(1, 20)
        worksheet.set_row(2, 15)
        worksheet.set_row(3, 15)
        worksheet.set_row(4, 15)
        worksheet.set_row(5, 20)
        worksheet.set_row(6, 20)
        row = 2
        row_set = row

        if self.date_from and self.date_to:
            date_2 = datetime.strftime(self.date_to, '%d-%m-%Y')
            date_1 = datetime.strftime(self.date_from, '%d-%m-%Y')
            asset_report_month = self.date_from.strftime("%B")
            worksheet.merge_range('A1:G2', 'Inventory Report For %s %s' % (asset_report_month, self.date_from.year),
                                  heading_format)
            worksheet.write('A3:A3', '', cell_text_format_n)
            worksheet.write('A4:A4', '', cell_text_format_n)
            worksheet.write('B3:B3', 'Company', cell_text_format_n)
            worksheet.merge_range('C3:E3', '%s' % self.company.name, cell_text_format_n)

            worksheet.write('B4:B4', 'Department', cell_text_format_n)
            if self.department_name:
                worksheet.merge_range('C4:E4', '%s' % self.department_id.name, cell_text_format_n)
            else:
                worksheet.merge_range('C4:E4', "All", cell_text_format_n)

            worksheet.write(row, 5, 'Date From', cell_text_format_n)
            worksheet.write(row, 6, date_1 or '', cell_date_text_format)
            row += 1
            worksheet.write(row, 5, 'Date To', cell_text_format_n)
            worksheet.write(row, 6, date_2 or '', cell_date_text_format)
            row += 2

            worksheet.write(row, 0, 'Item', cell_text_format)
            worksheet.write(row, 1, 'Department', cell_text_format)
            worksheet.write(row, 2, 'Received Date', cell_text_format)
            worksheet.write(row, 3, 'Quantity', cell_text_format)
            worksheet.write(row, 4, 'Unit Price', cell_text_format)
            worksheet.write(row, 5, 'Total Cost', cell_text_format)
            worksheet.write(row, 6, 'Received by', cell_text_format)

            department_stockin_inventory = self.env['inventory.stockin.lines'].sudo().search(
                [('department_id', '=', self.department_name), ('received_date', '<=', self.date_to),
                 ('received_date', '>=', self.date_from)])
            stockin_inventory_report = self.env['inventory.stockin.lines'].sudo().search(
                [('received_date', '<=', self.date_to), ('received_date', '>=', self.date_from)])

            ro = row + 1
            col = 0
            if department_stockin_inventory:
                for department_inventory in department_stockin_inventory:
                    item = department_inventory.product_id.name
                    department = department_inventory.department_name
                    received_date_format = datetime.strftime(department_inventory.received_date, '%d-%m-%Y')
                    quantity = department_inventory.quantity
                    unit_cost = department_inventory.unit_cost
                    total_cost = department_inventory.cost
                    received_by = department_inventory.receiver_id

                    worksheet.write(ro, col, item or '', cell_text_format_new)
                    worksheet.write(ro, col + 1, department or '', cell_text_format_new)
                    worksheet.write(ro, col + 2, received_date_format or '', cell_text_format_new)
                    worksheet.write(ro, col + 3, quantity or '', cell_text_format_new)
                    worksheet.write(ro, col + 4, unit_cost or '', cell_text_format_new)
                    worksheet.write(ro, col + 5, total_cost or '', cell_text_format_new)
                    worksheet.write(ro, col + 6, received_by or '', cell_text_format_new)
                    ro = ro + 1
            else:
                for all_inventory_available in stockin_inventory_report:
                    item = all_inventory_available.product_id.name
                    department = all_inventory_available.department_name
                    received_date_format = datetime.strftime(all_inventory_available.received_date, '%d-%m-%Y')
                    quantity = all_inventory_available.quantity
                    unit_cost = all_inventory_available.unit_cost
                    total_cost = all_inventory_available.cost
                    received_by = all_inventory_available.receiver_id

                    worksheet.write(ro, col, item or '', cell_text_format_new)
                    worksheet.write(ro, col + 1, department or '', cell_text_format_new)
                    worksheet.write(ro, col + 2, received_date_format or '', cell_text_format_new)
                    worksheet.write(ro, col + 3, quantity or '', cell_text_format_new)
                    worksheet.write(ro, col + 4, unit_cost or '', cell_text_format_new)
                    worksheet.write(ro, col + 5, total_cost or '', cell_text_format_new)
                    worksheet.write(ro, col + 6, received_by or '', cell_text_format_new)
                    ro = ro + 1

        workbook.close()
        file_download = base64.b64encode(fp.getvalue())
        fp.close()

        self = self.with_context(default_name=file_name, default_file_download=file_download)

        return {
            'name': 'Inventory Report Download',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'stockin.inventory.report.excel',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': self._context,
        }


class StockInInventoryReportExcel(models.TransientModel):
    _name = 'stockin.inventory.report.excel'
    _description = "StockIn Inventory report excel table"

    name = fields.Char('File Name', size=256, readonly=True)
    file_download = fields.Binary('Download Asset', readonly=True)


class StockOutInventoryListWizard(models.TransientModel):
    _name = 'stockout.inventory.report.wizard'

    department_id = fields.Many2one('hr.department', string='Department', required=False)
    department_name = fields.Integer(string='Department', related='department_id.id')
    date_from = fields.Date(string='Date From', required=True,
                            default=lambda self: fields.Date.to_string(date.today().replace(day=1)))
    date_to = fields.Date(string='Date To', required=True,
                          default=lambda self: fields.Date.to_string(
                              (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()))
    company = fields.Many2one('res.company', default=lambda self: self.env['res.company']._company_default_get(),
                              string="Company")

    @api.multi
    def get_report(self):
        file_name = _('Inventory report ' + str(self.date_from) + ' - ' + str(self.date_to) + ' report.xlsx')
        fp = BytesIO()

        workbook = xlsxwriter.Workbook(fp)
        heading_format = workbook.add_format({'align': 'center',
                                              'valign': 'vcenter',
                                              'bold': True,
                                              'size': 14,
                                              'fg_color': '#89A130', })
        heading_format.set_border()
        sub2_heading_format = workbook.add_format({'align': 'center',
                                                   'valign': 'vcenter',
                                                   'bold': True, 'size': 14})
        sub2_heading_format.set_border()
        dr_cr_format = workbook.add_format({'align': 'center',
                                            # 'valign': 'vcenter',
                                            'bold': True, 'size': 14})
        dr_cr_format.set_border()
        sub_heading_format = workbook.add_format({'align': 'left',
                                                  # 'valign': 'vcenter',
                                                  'bold': True, 'size': 14})
        sub_heading_format.set_border()
        cell_text_format_n = workbook.add_format({'align': 'center',
                                                  'bold': True, 'size': 9,
                                                  })
        cell_text_format_n.set_border()
        cell_photo_format = workbook.add_format({'align': 'center',

                                                 })
        cell_photo_format.set_border()
        cell_date_text_format = workbook.add_format({'align': 'left',
                                                     'size': 9,
                                                     })
        cell_date_text_format.set_border()

        approve_format = workbook.add_format({'align': 'left',
                                              'bold': False, 'size': 14,
                                              })

        cell_text_format = workbook.add_format({'align': 'left',
                                                'bold': True, 'size': 13,
                                                'fg_color': '#695B55',
                                                'font_color': 'white'
                                                })

        cell_text_format.set_border()
        cell_text_format_new = workbook.add_format({'align': 'left',
                                                    'size': 9,
                                                    'num_format': '#,###0.00',
                                                    })
        cell_text_format_new.set_border()
        cell_number_format = workbook.add_format({'align': 'right',
                                                  'bold': False, 'size': 9,
                                                  'num_format': '#,###0.00'})
        cell_number_format.set_border()
        worksheet = workbook.add_worksheet(
            'Inventory report ' + str(self.date_from) + ' - ' + str(self.date_to) + ' report.xlsx')
        normal_num_bold = workbook.add_format({'bold': True, 'num_format': '#,###0.00', 'size': 9, })
        normal_num_bold.set_border()
        worksheet.set_column('A:J', 20)
        # worksheet.set_default_row(45)

        worksheet.set_row(0, 20)
        worksheet.set_row(1, 20)
        worksheet.set_row(2, 15)
        worksheet.set_row(3, 15)
        worksheet.set_row(4, 15)
        worksheet.set_row(5, 20)
        worksheet.set_row(6, 20)
        row = 2
        row_set = row

        if self.date_from and self.date_to:
            date_2 = datetime.strftime(self.date_to, '%d-%m-%Y')
            date_1 = datetime.strftime(self.date_from, '%d-%m-%Y')
            asset_report_month = self.date_from.strftime("%B")
            worksheet.merge_range('A1:J2', 'Inventory Report For %s %s' % (asset_report_month, self.date_from.year),
                                  heading_format)
            worksheet.write('A3:A3', '', cell_text_format_n)
            worksheet.write('A4:A4', '', cell_text_format_n)
            worksheet.write('B3:B3', 'Company', cell_text_format_n)
            worksheet.merge_range('C3:E3', '%s' % self.company.name, cell_text_format_n)

            worksheet.write('B4:B4', 'Department', cell_text_format_n)
            if self.department_name:
                worksheet.merge_range('C4:E4', '%s' % self.department_id.name, cell_text_format_n)
            else:
                worksheet.merge_range('C4:E4', "All", cell_text_format_n)

            worksheet.write(row, 5, 'Date From', cell_text_format_n)
            worksheet.write(row, 6, date_1 or '', cell_date_text_format)
            row += 1
            worksheet.write(row, 5, 'Date To', cell_text_format_n)
            worksheet.write(row, 6, date_2 or '', cell_date_text_format)
            row += 2

            worksheet.write(row, 0, 'Item', cell_text_format)
            worksheet.write(row, 1, 'Department', cell_text_format)
            worksheet.write(row, 2, 'Requested Quantity', cell_text_format)
            worksheet.write(row, 3, 'Issued Quantity', cell_text_format)
            worksheet.write(row, 4, 'Requested Purpose', cell_text_format)
            worksheet.write(row, 5, 'Project', cell_text_format)
            worksheet.write(row, 6, 'Requested by', cell_text_format)
            worksheet.write(row, 7, 'Issued by', cell_text_format)
            worksheet.write(row, 8, 'Date', cell_text_format)
            worksheet.write(row, 9, 'Status', cell_text_format)

            # department_stockout_inventory = self.env['inventory.stockout.lines'].sudo().search(
            #     [('department', '=', self.department_id)])
            department_stockout_inventory = self.env['inventory.stockout.lines'].sudo().search(
                [('department_id', '=', self.department_name), ('requested_date', '<=', self.date_to),
                 ('requested_date', '>=', self.date_from)])
            stockin_inventory_report = self.env['inventory.stockout.lines'].sudo().search([])

            ro = row + 1
            col = 0
            if department_stockout_inventory:
                for department_inventory in department_stockout_inventory:
                    item = department_inventory.product_id.name
                    department = department_inventory.stockout_id.department_id.name
                    requested_quantity = department_inventory.requested_quantity
                    issued_quantity = department_inventory.issued_quantity
                    purpose = department_inventory.request_reason
                    project = department_inventory.project.name
                    requester = department_inventory.stockout_id.requester_id.name
                    issuer = department_inventory.stockout_id.issuer_id.name
                    request_date_format = datetime.strftime(department_inventory.requested_date, '%d-%m-%Y')
                    status = department_inventory.stockout_id.state

                    worksheet.write(ro, col, item or '', cell_text_format_new)
                    worksheet.write(ro, col + 1, department or '', cell_text_format_new)
                    worksheet.write(ro, col + 2, requested_quantity or '', cell_text_format_new)
                    worksheet.write(ro, col + 3, issued_quantity or '', cell_text_format_new)
                    worksheet.write(ro, col + 4, purpose or '', cell_text_format_new)
                    worksheet.write(ro, col + 5, project or '', cell_text_format_new)
                    worksheet.write(ro, col + 6, requester or '', cell_text_format_new)
                    worksheet.write(ro, col + 7, issuer or '', cell_text_format_new)
                    worksheet.write(ro, col + 8, request_date_format or '', cell_text_format_new)
                    worksheet.write(ro, col + 9, status or '', cell_text_format_new)
                    ro = ro + 1
            else:
                for all_inventory_available in stockin_inventory_report:
                    item = all_inventory_available.product_id.name
                    department = all_inventory_available.stockout_id.department_id.name
                    requested_quantity = all_inventory_available.requested_quantity
                    issued_quantity = all_inventory_available.issued_quantity
                    purpose = all_inventory_available.request_reason
                    project = all_inventory_available.project.name
                    requester = all_inventory_available.stockout_id.requester_id.name
                    issuer = all_inventory_available.stockout_id.issuer_id.name
                    # request_date_format = datetime.strftime(department_inventory.requested_date, '%d-%m-%Y')
                    request_date_format = all_inventory_available.requested_date
                    status = all_inventory_available.stockout_id.state

                    worksheet.write(ro, col, item or '', cell_text_format_new)
                    worksheet.write(ro, col + 1, department or '', cell_text_format_new)
                    worksheet.write(ro, col + 2, requested_quantity or '', cell_text_format_new)
                    worksheet.write(ro, col + 3, issued_quantity or '', cell_text_format_new)
                    worksheet.write(ro, col + 4, purpose or '', cell_text_format_new)
                    worksheet.write(ro, col + 5, project or '', cell_text_format_new)
                    worksheet.write(ro, col + 6, requester or '', cell_text_format_new)
                    worksheet.write(ro, col + 7, issuer or '', cell_text_format_new)
                    worksheet.write(ro, col + 8, request_date_format or '', cell_text_format_new)
                    worksheet.write(ro, col + 9, status or '', cell_text_format_new)
                    ro = ro + 1

        workbook.close()
        file_download = base64.b64encode(fp.getvalue())
        fp.close()

        self = self.with_context(default_name=file_name, default_file_download=file_download)

        return {
            'name': 'Inventory Report Download',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'stockout.inventory.report.excel',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': self._context,
        }


class StockOutInventoryReportExcel(models.TransientModel):
    _name = 'stockout.inventory.report.excel'
    _description = "StockOut Inventory report excel table"

    name = fields.Char('File Name', size=256, readonly=True)
    file_download = fields.Binary('Download Asset', readonly=True)