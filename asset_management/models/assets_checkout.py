from odoo import models, fields, api, _


class AccountAssetCheckout(models.Model):
    _name = 'account.asset.checkout'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    SELECTION = [
        ("draft", "Draft"),
        ("submit", "Submitted"),
        ("line_manager", "Line Manager"),
        ("procurement", "Procurement"),
        ("adm_cd", "AD Manager/ Country Director"),
        ("staff", "Confirm Receipt"),
    ]

    @api.multi
    def button_submit(self):
        self.write({'state': 'submit'})
        return True

    @api.multi
    def button_line_manager_review(self):
        self.write({'state': 'line_manager'})
        return True

    @api.multi
    def button_procurement_review(self):
        self.write({'state': 'procurement'})
        for asset in self.asset_name:
            asset.write({'state': 'inuse'})
        return True

    @api.multi
    def button_am_manager_review(self):
        self.write({'state': 'adm_cd'})
        return True

    @api.multi
    def button_confirm_receipt(self):
        self.write({'state': 'staff'})
        return True

    def _default_employee(self):
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        if employee:
            return employee.id

    name = fields.Many2one(comodel_name='hr.employee', string='Employee Name',
                           required=True,  default=_default_employee)
    state = fields.Selection(SELECTION, index=True, track_visibility='onchange',
                             default='draft')
    employee_no = fields.Char(string='Employee Number', related='name.work_phone')
    position = fields.Char(string='Position/Title', related='name.job_id.name')
    department = fields.Char(string='Department', related='name.department_id.name')
    phone = fields.Char(string='Phone', related='name.work_phone')
    email = fields.Char(string='Email', related='name.work_email')

    # Asset information
    asset_category = fields.Many2one(comodel_name="account.asset.category", string="Asset Name")
    asset_name = fields.Many2one(comodel_name="account.asset.asset", string="Assign Asset")
    identification_number = fields.Char(string="Code", related="asset_name.code")
    taken_date = fields.Date(string="Taken Date")
    returning_date = fields.Date(string="Returning Date")

    purpose = fields.Text(string="Purpose", comment="Please write in detail regarding purpose")
    comment = fields.Text(string="Comments", comment="Please write in detail regarding purpose")

    # Custodian  inform
    custodian_name = fields.Many2one(comodel_name='hr.employee', string='Custodian Name',
                                     required=False)
    custodian_job_title = fields.Char(string="Job Title", related="custodian_name.job_id.name")
    id_no = fields.Char(string="ID Number", related="custodian_name.work_phone")
