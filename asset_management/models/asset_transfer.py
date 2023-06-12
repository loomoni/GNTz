from odoo import models, fields, api, _


class AccountAssetTransfer(models.Model):
    _name = 'account.asset.transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    SELECTION = [
        ("draft", "Draft"),
        # ("line_manager", "Line Manager"),
        ("procurement", "Procurement"),
        ("adm_cd", "AD Manager"),
        ("country_director", "Country Director"),
        ("staff", "Confirm Receipt"),
    ]

    @api.multi
    def button_line_manager_review(self):
        self.write({'state': 'line_manager'})
        return True

    @api.multi
    def button_procurement_review(self):
        self.write({'state': 'procurement'})
        return True

    @api.multi
    def button_am_manager_review(self):
        self.write({'state': 'adm_cd'})
        return True

    def _default_employee(self):
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        if employee:
            return employee.id

    name = fields.Many2one(comodel_name='hr.employee', string='Employee Name',
                           required=True, default=_default_employee, readonly=True)
    state = fields.Selection(SELECTION, index=True, track_visibility='onchange',
                             default='draft')
    employee_no = fields.Char(string='Employee Number', related='name.work_phone')
    position = fields.Char(string='Position/Title', related='name.job_id.name')
    department = fields.Char(string='Department', related='name.department_id.name')
    phone = fields.Char(string='Phone', related='name.work_phone')
    email = fields.Char(string='Email', related='name.work_email')

    # Custodian  inform
    custodian_name = fields.Many2one(comodel_name='hr.employee', string='Custodian Name',
                                     required=False)
    custodian_job_title = fields.Char(string="Job Title", related="custodian_name.job_id.name")
    id_no = fields.Char(string="ID Number", related="custodian_name.work_phone")

    asset_hand_over_line_ids = fields.One2many(comodel_name='account.asset.hand.over.lines',
                                               string="Asset IDS",
                                               inverse_name="asset_hand_over_ids")


class AccountAssetHandOverLines(models.Model):
    _name = 'account.asset.hand.over.lines'

    # Asset information account.asset.assign related="asset_name.code"
    asset_name = fields.Many2one(comodel_name="account.asset.assign", string="Asset")
    identification_number = fields.Char(string="Code")
    asset_condition = fields.Char(string="Asset condition")
    handover_reason = fields.Text(string="Reason for Asset Handover")
    asset_hand_over_ids = fields.Many2one('account.asset.transfer', string="Asset HandOver ID")
