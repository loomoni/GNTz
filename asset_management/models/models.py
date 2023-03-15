# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import random, string
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare, float_is_zero
from dateutil.relativedelta import relativedelta
import calendar


class AssetsInherit(models.Model):
    _inherit = 'account.asset.asset'

    ASSET_ORIGIN_SELECTION = [
        ("donated", "Donations"),
        ("pre_existing", "Pre Existing"),
        ("procured", "Procured"),
    ]

    SELECTION = [
        ('draft', 'Draft'),
        ('open', 'Unassigned'),
        ('inuse', 'Running'),
        ('repair', 'Repair'),
        ('replace', 'Replace'),
        ('close', 'Close')
    ]
    state = fields.Selection(SELECTION, 'Status', required=True, copy=False, default='draft',
                             help="When an asset is created, the status is 'Draft'.\n"
                                  "If the asset is confirmed, the status goes in 'Running' and the depreciation lines can be posted in the accounting.\n"
                                  "You can manually close an asset when the depreciation is over. If the last line of depreciation is posted, the asset automatically goes in that status.")

    @api.depends('category_id.asset_category_code')
    def _default_serial_no(self):
        x = self.env['account.asset.asset'].sudo().search_count([]) + 1
        code = self.category_id.asset_category_code
        return 'GNTZ' + '-' + str(x)

    # @api.depends('department_id')
    # def _default_serial_no(self):
    #     x = self.env['account.asset.asset'].sudo().search_count([]) + 1
    #     department_code = ''
    #     if self.department_id:
    #         try:
    #             department_code = self.department_id.code
    #         except:
    #             pass
    #     return 'GNTZ-' + str(department_code) + '-' + str(x)

    def _default_department(self):
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        if employee and employee.department_id:
            return employee.department_id.id

    code = fields.Char(string='Asset Number', size=32, readonly=True, required=True,
                       states={'draft': [('readonly', False)]}, default=_default_serial_no)
    cummulative_amount = fields.Float(string='Accumulated Depreciation', compute='_compute_accumulated_depreciation',
                                      method=True, digits=0)
    asset_origin = fields.Selection(ASSET_ORIGIN_SELECTION, index=True, track_visibility='onchange',
                                    default='procured')
    department_id = fields.Many2one('hr.department', string='Asset Location/Department', required=True,
                                    default=_default_department, store=True)
    branch = fields.Char(string='Branch', related='department_id.branch_id.name')
    asset_id_no = fields.Char(string='ASSET ID #')
    account_id = fields.Many2one('account.account', string='Credit Account')
    journal_id = fields.Many2one('account.journal', string='Credit Account Journal')

    _sql_constraints = [
        ('code_unique',
         'unique(code)',
         'Choose another reference no - it has to be unique!')
    ]

    @api.onchange('journal_id')
    def onchange_journal_id(self):
        if self.journal_id:
            if not self.journal_id.default_credit_account_id:
                raise UserError(
                    'Please add a default Credit Account to the Journal Setup')
            else:
                self.account_id = self.journal_id.default_credit_account_id.id

    @api.one
    @api.depends('value', 'depreciation_line_ids.move_check', 'depreciation_line_ids.amount')
    def _compute_accumulated_depreciation(self):
        total_amount = 0.0
        for line in self.depreciation_line_ids:
            if line.move_check:
                total_amount += line.amount
        self.cummulative_amount = total_amount

    @api.model
    def create(self, vals):
        asset = super(AssetsInherit, self.with_context(mail_create_nolog=True)).create(vals)
        asset.sudo().compute_depreciation_board()
        return asset

    @api.multi
    def compute_depreciation_board(self):
        self.ensure_one()

        posted_depreciation_line_ids = self.depreciation_line_ids.filtered(lambda x: x.move_check).sorted(
            key=lambda l: l.depreciation_date)
        unposted_depreciation_line_ids = self.depreciation_line_ids.filtered(lambda x: not x.move_check)

        # Remove old unposted depreciation lines. We cannot use unlink() with One2many field
        commands = [(2, line_id.id, False) for line_id in unposted_depreciation_line_ids]

        if self.value_residual != 0.0:
            amount_to_depr = residual_amount = self.value_residual

            # if we already have some previous validated entries, starting date is last entry + method period
            if posted_depreciation_line_ids and posted_depreciation_line_ids[-1].depreciation_date:
                last_depreciation_date = fields.Date.from_string(posted_depreciation_line_ids[-1].depreciation_date)
                depreciation_date = last_depreciation_date + relativedelta(months=+self.method_period)
            else:
                # depreciation_date computed from the purchase date
                depreciation_date = self.date
                if self.date_first_depreciation == 'last_day_period':
                    # depreciation_date = the last day of the month
                    depreciation_date = depreciation_date + relativedelta(day=31)
                    # ... or fiscalyear depending the number of period
                    if self.method_period == 12:
                        depreciation_date = depreciation_date + relativedelta(
                            month=self.company_id.fiscalyear_last_month)
                        depreciation_date = depreciation_date + relativedelta(day=self.company_id.fiscalyear_last_day)
                        if depreciation_date < self.date:
                            depreciation_date = depreciation_date + relativedelta(years=1)
                elif self.first_depreciation_manual_date and self.first_depreciation_manual_date != self.date:
                    # depreciation_date set manually from the 'first_depreciation_manual_date' field
                    depreciation_date = self.first_depreciation_manual_date

            total_days = (depreciation_date.year % 4) and 365 or 366
            month_day = depreciation_date.day
            undone_dotation_number = self._compute_board_undone_dotation_nb(depreciation_date, total_days)

            for x in range(len(posted_depreciation_line_ids), undone_dotation_number):
                sequence = x + 1
                amount = self._compute_board_amount(sequence, residual_amount, amount_to_depr, undone_dotation_number,
                                                    posted_depreciation_line_ids, total_days, depreciation_date)
                amount = self.currency_id.round(amount)
                if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                    continue
                residual_amount -= amount
                vals = {
                    'amount': amount,
                    'asset_id': self.id,
                    'sequence': sequence,
                    'name': (self.code or '') + '/' + str(sequence),
                    'remaining_value': residual_amount + self.salvage_value,
                    'depreciated_value': self.value - (self.salvage_value + residual_amount),
                    'depreciation_date': depreciation_date,
                }
                commands.append((0, False, vals))

                depreciation_date = depreciation_date + relativedelta(months=+self.method_period)

                if month_day > 28 and self.date_first_depreciation == 'manual':
                    max_day_in_month = calendar.monthrange(depreciation_date.year, depreciation_date.month)[1]
                    depreciation_date = depreciation_date.replace(day=min(max_day_in_month, month_day))

                # datetime doesn't take into account that the number of days is not the same for each month
                if not self.prorata and self.method_period % 12 != 0 and self.date_first_depreciation == 'last_day_period':
                    max_day_in_month = calendar.monthrange(depreciation_date.year, depreciation_date.month)[1]
                    depreciation_date = depreciation_date.replace(day=max_day_in_month)

        self.write({'depreciation_line_ids': commands})

        return True

    @api.multi
    def validate(self):
        self.write({'state': 'open'})
        fields = [
            'method',
            'method_number',
            'method_period',
            'method_end',
            'method_progress_factor',
            'method_time',
            'salvage_value',
            'invoice_id',
        ]
        ref_tracked_fields = self.env['account.asset.asset'].fields_get(fields)
        for asset in self:
            tracked_fields = ref_tracked_fields.copy()
            if asset.method == 'linear':
                del (tracked_fields['method_progress_factor'])
            if asset.method_time != 'end':
                del (tracked_fields['method_end'])
            else:
                del (tracked_fields['method_number'])
            dummy, tracking_value_ids = asset._message_track(tracked_fields, dict.fromkeys(fields))
            asset.message_post(subject=_('Asset created'), tracking_value_ids=tracking_value_ids)

            if asset.asset_origin is not False:
                if asset.asset_origin == 'donated':
                    move_line_1 = {
                        'name': asset.name,
                        'account_id': asset.category_id.account_asset_id.id,
                        'credit': 0.0,
                        'debit': asset.value,
                        'currency_id': asset.company_id.currency_id != asset.currency_id and asset.currency_id.id or False,
                        'amount_currency': asset.company_id.currency_id != asset.currency_id and asset.value or 0.0,
                    }
                    move_line_2 = {
                        'name': asset.name,
                        'account_id': asset.account_id.id,
                        'debit': 0.0,
                        'credit': asset.value,
                        'currency_id': asset.company_id.currency_id != asset.currency_id and asset.currency_id.id or False,
                        'amount_currency': asset.company_id.currency_id != asset.currency_id and asset.value or 0.0,
                    }

                    move_vals = {
                        'ref': asset.code,
                        'date': asset.date,
                        'journal_id': asset.journal_id.id,
                        'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
                    }
                    move = self.env['account.move'].create(move_vals)


class AssetAssign(models.Model):
    _name = 'account.asset.assign'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'asset_name'

    STATE_SELECTION = [
        ("draft", "Draft"),
        ("send_request", "Requested"),
        ("line_manager", "Line Manager"),
        ("procurement", "Procurement"),
        ("assigned", "Assign"),
        ("unassigned", "Unassign"),
    ]

    date_created = fields.Date('Date / Time', readonly=True, required=True, index=True,
                               default=fields.date.today(), store=True)
    attachment = fields.Binary(string="Attachment", attachment=True, store=True, )
    attachment_name = fields.Char('Attachment Name')
    assignment_no = fields.Char('Assignment No', readonly=True, store=True)
    assigned_by = fields.Many2one('res.users', 'Assigned By', default=lambda self: self.env.uid, readonly=True)
    assigned_person = fields.Many2one('hr.employee', 'Assigned Person', default=lambda self: self.env.uid, )
    job_title = fields.Char(string="Job title", related='assigned_person.job_title')
    id_number = fields.Char(string="ID Number", related='assigned_person.work_phone')
    assigned_location = fields.Many2one('account.asset_location', 'Assigned Location')
    asset_ids = fields.Many2many('account.asset.asset', string="Assets To Assign")
    asset_name = fields.Char(string='Asset Name', related='asset_ids.name')
    asset_category = fields.Char(string='Asset Category', related='asset_ids.category_id.name')
    asset_number = fields.Char(string='Asset Number', related='asset_ids.code')
    asset_branch = fields.Char(string='Asset Branch', related='asset_ids.branch')
    asset_category_ids = fields.One2many(comodel_name='account.asset.assign.category.line', string="Assets Category",
                                         inverse_name="category_line_id")
    state = fields.Selection(STATE_SELECTION, index=True, track_visibility='onchange', required=True, copy=False,
                             default='draft')

    @api.model
    def create(self, vals):
        ticketNumber = self.env["account.asset.assign"].search_count([])
        vals['assignment_no'] = 'ASSET/ASSIGN/' + str(ticketNumber + 1)
        res = super(AssetAssign, self).create(vals)
        return res

    @api.multi
    def button_staff_or_line_manager_request(self):
        for asset in self.asset_ids:
            asset.write({'send_request': True})
        self.write({'state': 'send_request'})
        return True

    @api.multi
    def button_line_manager_review(self):
        for asset in self.asset_ids:
            asset.write({'line_manager': True})
        self.write({'state': 'line_manager'})
        return True

    @api.multi
    def button_procurement_assign(self):
        for asset in self.asset_ids:
            asset.write({'procurement': True})
            asset.write({'state': 'inuse'})
        self.write({'state': 'procurement'})
        return True

    @api.multi
    def button_assign(self):
        for asset in self.asset_ids:
            asset.write({'assigned': True})
        self.write({'state': 'assigned'})
        return True

    @api.multi
    def button_unassign(self):
        for asset in self.asset_ids:
            asset.write({'assigned': False})
        self.write({'state': 'unassigned'})
        return True


class AssetAssignmentCategory(models.Model):
    _name = 'account.asset.assign.category.line'

    name = fields.Many2one('account.asset.category', string='Asset')
    category_line_id = fields.Many2one('account.asset.assign', string='assign category id')


class AssetInherited(models.Model):
    _inherit = 'account.asset.asset'
    assigned = fields.Boolean(default=False, sting='Asset Assigned')
    method_progress_factor = fields.Float(string='Degressive Factor', readonly=True, digits=(12, 4), default=0.3000,
                                          states={'draft': [('readonly', False)]})


class AssetCategoryInherited(models.Model):
    _inherit = 'account.asset.category'

    asset_category_code = fields.Char(string="Category Code")
    account_depreciation_id = fields.Many2one('account.account', string='Depreciation Entries: Credit Account',
                                              required=True,
                                              domain=[('internal_type', '=', 'other'), ('deprecated', '=', False)],
                                              help="Account used in the depreciation entries, to decrease the asset value.")
    account_depreciation_expense_id = fields.Many2one('account.account', string='Depreciation Entries: Debit Account',
                                                      required=True, domain=[('internal_type', '=', 'other'),
                                                                             ('deprecated', '=', False)],
                                                      oldname='account_income_recognition_id',
                                                      help="Account used in the periodical entries, to record a part of the asset as expense.")
    method_progress_factor = fields.Float('Degressive Factor', digits=(12, 4), default=0.3000)
