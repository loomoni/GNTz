# -*- coding: utf-8 -*-
# import base64
import imghdr
from datetime import *
from io import BytesIO

# from pandas.io.sas.sas_constants import magic

from odoo import models, http
from odoo.http import request
from PIL import Image
import io

import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell

from odoo import models, fields, api, _
import random, string
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare, float_is_zero, datetime
from dateutil.relativedelta import relativedelta
import calendar

import qrcode
import base64


class AssetQRCodeReport(models.AbstractModel):
    _name = 'report.asset_management_qr_code_template'
    _description = 'Asset QR Code Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        assets = self.env['asset.asset'].browse(docids)
        return {
            'docs': assets,
        }


class AssetsInherit(models.Model):
    _inherit = 'account.asset.asset'
    _name = "account.asset.asset"

    ASSET_ORIGIN_SELECTION = [
        ("donated", "Donations"),
        ("pre_existing", "Pre Existing"),
        ("procured", "Procured"),
    ]

    SELECTION = [
        ('draft', 'Draft'),
        ('fixed', 'Fixed Asset'),
        ('non_fixed', 'Non-Fixed Asset'),
        ('review', 'Finance Reviewed'),
        ('open', 'Unassigned'),
        ('inuse', 'Running'),
        ('repair', 'Repair'),
        ('replace', 'Replace'),
        ('close', 'Close')
    ]

    @api.multi
    def back_to_draft(self):
        self.write({'state': 'draft'})
        return True

    @api.multi
    def button_procurement_register_fixed_asset(self):
        self.write({'state': 'fixed'})
        return True

    @api.multi
    def button_procurement_register_non_fixed_asset(self):
        self.write({'state': 'non_fixed'})
        return True

    @api.multi
    def button_finance_review(self):
        self.write({'state': 'review'})
        return True

    @api.multi
    def button_finance_back_to_draft(self):
        self.write({'state': 'draft'})
        return True

    @api.multi
    def button_reject(self):
        self.write({'state': 'close'})
        return True

    name = fields.Char(string="name", readonly=True)
    state = fields.Selection(SELECTION, 'Status', required=True, copy=False, default='draft',
                             help="When an asset is created, the status is 'Draft'.\n"
                                  "If the asset is confirmed, the status goes in 'Running' and the depreciation lines can be posted in the accounting.\n"
                                  "You can manually close an asset when the depreciation is over. If the last line of depreciation is posted, the asset automatically goes in that status.")

    @api.multi
    def unlink(self):
        for asset in self:
            if asset.state in ('open', 'inuse', 'repair', 'repair', 'close'):
                raise ValidationError(_("You cannot delete an approved asset."))
        return super(AssetsInherit, self).unlink()

    # @api.model
    # def fields_get(self, allfields=None, attributes=None):
    #     res = super(AssetsInherit, self).fields_get(allfields, attributes)
    #     for record in self:
    #         if record.state in ['open', 'inuse']:
    #             for field_name in res:
    #                 # Make all fields readonly for assets in 'open' and 'running' state
    #                 res[field_name]['readonly'] = True
    #     return res

    # @api.model
    # def fields_get(self, allfields=None, attributes=None):
    #     res = super(AssetsInherit, self).fields_get(allfields, attributes)
    #     for record in self:
    #         if record.state in ['open', 'inuse']:
    #             for field_name in res:
    #                 if 'readonly' not in res[field_name]['attrs']:
    #                     res[field_name]['attrs'] = {'readonly': [(True, '1')]}
    #     return res

    @api.depends('department_id.branch_id.code', 'category_id.asset_category_code')
    def _default_serial_no(self):
        asset_count = self.env['account.asset.asset'].search_count([])
        for record in self:
            branch_code = str(record.department_id.branch_id.code) if record.department_id.branch_id.code else ""
            category_code = str(
                record.category_id.asset_category_code) if record.category_id.asset_category_code else ""

            record.code = 'GNTZ' + '-' + branch_code + '-' + category_code + '-' + str(asset_count + 1)

    def _default_department(self):
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        if employee and employee.department_id:
            return employee.department_id.id

    code = fields.Char(string='Asset Number', searchable=True, compute='_default_serial_no', store=True, readonly=False)
    # code = fields.Char(string='Asset Number', readonly=False)
    cummulative_amount = fields.Float(string='Accumulated Depreciation', compute='_compute_accumulated_depreciation',
                                      method=True, digits=0)
    asset_origin = fields.Selection(ASSET_ORIGIN_SELECTION, index=True, track_visibility='onchange',
                                    default='procured')
    department_id = fields.Many2one('hr.department', string='Asset Location/Department', required=True,
                                    default=_default_department, store=True)
    branch = fields.Char(string='Branch', related='department_id.branch_id.name')
    name = fields.Char(readonly=False)
    method = fields.Selection(readonly=False)
    value = fields.Float(readonly=False)
    salvage_value = fields.Float(readonly=False)
    value_residual = fields.Float(readonly=False)
    method_number = fields.Integer(readonly=False)
    method_period = fields.Integer(readonly=False)
    date = fields.Date(readonly=False)
    method_progress_factor = fields.Float(readonly=False)
    category_id = fields.Many2one(readonly=False)
    asset_id_no = fields.Char(string='ASSET ID #')
    account_id = fields.Many2one('account.account', string='Credit Account')
    journal_id = fields.Many2one('account.journal', string='Credit Account Journal')
    image_small = fields.Binary("Photo", attachment=True)
    supportive_document_line_ids = fields.One2many(comodel_name='account.asset.support.document.line',
                                                   string="Supportive Document",
                                                   inverse_name="document_ids")
    insurance_model_line_ids = fields.One2many(comodel_name='insurance.model.line',
                                               string="Insurance IDS",
                                               inverse_name="insurance_ids")
    service_model_line_ids = fields.One2many(comodel_name='service.model.line',
                                             string="Service IDS",
                                             inverse_name="service_ids")
    description_line_ids = fields.One2many(comodel_name='description.line',
                                           string="description IDS",
                                           inverse_name="description_ids")
    asset_assignment_line_ids = fields.One2many(comodel_name='account.asset.assign',
                                                string="Asset Assignment IDS",
                                                inverse_name="asset_ids")

    # asset_assignment_ids = fields.Many2many(comodel_name='account.asset.assign', string="Assets Assignment",
    #                                         inverse_name="asset_ids")

    # _sql_constraints = [
    #     ('code_unique',
    #      'unique(code)',
    #      'Choose another reference no - it has to be unique!')
    # ]

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


class AccountAssetAssignWizard(models.TransientModel):
    _name = 'account.asset.assign.wizard'

    department_id = fields.Many2one('hr.department', string='Department', required=False)
    department_name = fields.Integer(string='Department', related='department_id.id')
    print_date = fields.Datetime(string='Date', default=lambda self: fields.Datetime.now(), readonly=True)

    @api.multi
    def get_report(self):
        file_name = _('GNTZ ASSET CUSTODIAN FORM ' ' report.xlsx')
        fp = BytesIO()

        workbook = xlsxwriter.Workbook(fp)
        worksheet = workbook.add_worksheet()

        # Define the heading format
        heading_format = workbook.add_format({
            # 'bold': True,
            'font_size': 7,
            'font_name': 'Arial',
            # 'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
        })
        heading_format.set_border()
        title_format = workbook.add_format({
            'bold': True,
            'font_name': 'Arial',
            'font_size': 14,
            'align': 'center',
            # 'valign': 'vcenter',
            'text_wrap': True,
        })
        title_format.set_border()

        cell_text_info_format = workbook.add_format({
            'bold': True,
            'font_name': 'Arial',
            'font_size': 8,
            'text_wrap': True,
        })
        cell_text_info_format.set_border()
        cell_text_info_body_format = workbook.add_format({
            'bold': True,
            'font_name': 'Arial',
            'font_size': 8,
            'align': 'center',
            'text_wrap': True,
        })
        cell_text_info_body_format.set_border()
        cell_text_sub_title_format = workbook.add_format({
            'bold': True,
            'font_name': 'Arial',
            'font_size': 8,
            'text_wrap': True,
        })
        cell_text_sub_title_format.set_border()

        cell_text_body_format = workbook.add_format({
            'font_name': 'Arial',
            'font_size': 8,
            'text_wrap': True,
        })
        cell_text_body_format.set_border()
        divider_format = workbook.add_format({'fg_color': '#9BBB59', })
        # divider_format = workbook.add_format({'fg_color': '#89A130', })
        divider_format.set_border()
        worksheet.set_row(0, 85)
        worksheet.set_column('A:E', 13)
        # worksheet.merge_range('A1:F1', '')
        company = self.env.user.company_id

        # Get the logged-in user's name
        user = request.env.user
        user_name = user.name
        email = user.login
        job_position = ''
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id), ('job_id', '!=', False)],
                                                            limit=1)
        if employee:
            job_position = employee.job_id.name or ''

        # Find the department name of the employee
        department_name = ''
        if employee and employee.department_id:
            department_name = employee.department_id.name or ''

        company_info = "\n".join(filter(None, [company.name, company.street2, company.street, company.city,
                                               company.country_id.name,
                                               'Phone: ' + company.phone + ' Email: ' + company.email + ' Web: ' + company.website]))
        worksheet.merge_range('A1:I1', company_info, heading_format)

        # Convert the logo from base64 to binary data
        logo_data = base64.b64decode(company.logo)

        # Create a BytesIO object to hold the image data
        image_stream = BytesIO(logo_data)
        # Add the logo to the worksheet
        worksheet.insert_image('F1', 'logo.png', {'image_data': image_stream, 'x_scale': 0.43, 'y_scale': 0.43})

        # Merge cells for the logo in F1:G2
        # worksheet.merge_range('F1:G2', '')  # Merge the cells
        worksheet.set_row(1, 26)
        worksheet.merge_range('A2:I2', 'GNTZ ASSET CUSTODIAN FORM', title_format)

        worksheet.set_row(2, 12)
        worksheet.set_row(6, 12)
        worksheet.merge_range('A3:I3', '', divider_format)
        worksheet.merge_range('A7:I7', '', divider_format)

        worksheet.write('A4:A4', 'Extracted by', cell_text_info_format)
        worksheet.merge_range('B4:D4', user_name, cell_text_info_body_format)

        worksheet.write('A5:A5', 'Date', cell_text_info_format)
        worksheet.merge_range('B5:I5', datetime.now().strftime('%m-%d-%Y'), cell_text_info_body_format)

        worksheet.write('A6:A6', 'Email', cell_text_info_format)
        worksheet.merge_range('B6:D6', email, cell_text_info_body_format)

        worksheet.write('E4:E4', 'Designation', cell_text_info_format)
        worksheet.merge_range('F4:I4', job_position, cell_text_info_body_format)

        worksheet.write('E6:E6', 'Department', cell_text_info_format)
        worksheet.merge_range('F6:I6', department_name, cell_text_info_body_format)

        worksheet.write('A8:A8', 'S/N', cell_text_sub_title_format)
        worksheet.write('B8:B8', 'Request', cell_text_sub_title_format)
        worksheet.write('C8:C8', 'Department', cell_text_sub_title_format)
        worksheet.write('D8:D8', 'Asset Name', cell_text_sub_title_format)
        worksheet.write('E8:E8', 'Asset ID', cell_text_sub_title_format)
        worksheet.write('F8:F8', 'Asset No', cell_text_sub_title_format)
        worksheet.write('G8:G8', 'Purchased Date', cell_text_sub_title_format)
        worksheet.write('H8:H8', 'Gross Value', cell_text_sub_title_format)
        worksheet.write('I8:I8', 'Condition', cell_text_sub_title_format)

        department_asset_custodian = self.env['account.asset.assign'].sudo().search(
            [('assigned_person.department_id', '=', self.department_name)])
        all_asset_custodian = self.env['account.asset.assign'].sudo().search([])

        row = 8
        col = 0
        index = 1

        if department_asset_custodian:
            for department_custodian in department_asset_custodian:
                index = index
                assigned_person = department_custodian.assigned_person.name
                department = department_custodian.assigned_person.department_id.name
                for asset in department_custodian.asset_ids:
                    asset_name = asset.name
                    asset_id = asset.asset_id_no
                    asset_no = asset.code
                    purchase_date = datetime.strftime(asset.date, '%d-%m-%Y')
                    gross_value = asset.value

                    worksheet.write(row, col, index or '', cell_text_body_format)
                    worksheet.write(row, col + 1, assigned_person or '', cell_text_body_format)
                    worksheet.write(row, col + 2, department or '', cell_text_body_format)
                    worksheet.write(row, col + 3, asset_name or '', cell_text_body_format)
                    worksheet.write(row, col + 4, asset_id or '', cell_text_body_format)
                    worksheet.write(row, col + 5, asset_no or '', cell_text_body_format)
                    worksheet.write(row, col + 6, purchase_date or '', cell_text_body_format)
                    worksheet.write(row, col + 7, gross_value or '', cell_text_body_format)
                    worksheet.write(row, col + 8, '' or '', cell_text_body_format)
                    row = row + 1
                    index = index + 1
        else:
            for all_asset in all_asset_custodian:
                index = index
                assigned_person = all_asset.assigned_person.name
                department = all_asset.assigned_person.department_id.name
                for asset in all_asset.asset_ids:
                    asset_name = asset.name
                    asset_id = asset.asset_id_no
                    asset_no = asset.code
                    purchase_date = datetime.strftime(asset.date, '%d-%m-%Y')
                    gross_value = asset.value

                    worksheet.write(row, col, index or '', cell_text_body_format)
                    worksheet.write(row, col + 1, assigned_person or '', cell_text_body_format)
                    worksheet.write(row, col + 2, department or '', cell_text_body_format)
                    worksheet.write(row, col + 3, asset_name or '', cell_text_body_format)
                    worksheet.write(row, col + 4, asset_id or '', cell_text_body_format)
                    worksheet.write(row, col + 5, asset_no or '', cell_text_body_format)
                    worksheet.write(row, col + 6, purchase_date or '', cell_text_body_format)
                    worksheet.write(row, col + 7, gross_value or '', cell_text_body_format)
                    worksheet.write(row, col + 8, '' or '', cell_text_body_format)
                    row = row + 1
                    index = index + 1

        workbook.close()
        file_download = base64.b64encode(fp.getvalue())
        fp.close()

        self = self.with_context(default_name=file_name, default_file_download=file_download)

        return {
            'name': 'Asset Custodian Report',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'asset.custodian.excel',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': self._context,
        }


class AssetCustodianReportExcel(models.TransientModel):
    _name = 'asset.custodian.excel'
    _description = "Asset Custodian excel table"

    name = fields.Char('File Name', size=256, readonly=True)
    file_download = fields.Binary('Download Custodian Report', readonly=True)


class AssetListWizard(models.TransientModel):
    _name = 'asset.list.wizard'

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
        file_name = _('Asset report ' + str(self.date_from) + ' - ' + str(self.date_to) + ' report.xlsx')
        fp = BytesIO()

        workbook = xlsxwriter.Workbook(fp)
        worksheet = workbook.add_worksheet()
        # Disable gridlines
        worksheet.hide_gridlines(2)  # 2 means 'both'

        # Define the heading format
        heading_format = workbook.add_format({
            # 'bold': True,
            'font_size': 7,
            'font_name': 'Arial',
            # 'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
        })
        heading_format.set_border()
        title_format = workbook.add_format({
            'bold': True,
            'font_name': 'Arial',
            'font_size': 14,
            'align': 'center',
            # 'valign': 'vcenter',
            'text_wrap': True,
        })
        title_format.set_border()

        cell_text_info_format = workbook.add_format({
            'bold': True,
            'font_name': 'Arial',
            'font_size': 8,
            'text_wrap': True,
        })
        cell_text_info_format.set_border()
        cell_text_info_body_format = workbook.add_format({
            'bold': True,
            'font_name': 'Arial',
            'font_size': 8,
            'align': 'center',
            'text_wrap': True,
        })
        cell_text_info_body_format.set_border()
        cell_text_sub_title_format = workbook.add_format({
            'bold': True,
            'font_name': 'Arial',
            'font_size': 8,
            'text_wrap': True,
        })
        cell_text_sub_title_format.set_border()

        cell_text_body_format = workbook.add_format({
            'font_name': 'Arial',
            'font_size': 8,
            'num_format': '#,##0',
            'text_wrap': True,
        })
        cell_text_body_format.set_border()
        divider_format = workbook.add_format({'fg_color': '#9BBB59', })
        # divider_format = workbook.add_format({'fg_color': '#89A130', })
        divider_format.set_border()
        worksheet.set_row(0, 85)
        worksheet.set_column('A:E', 13)
        # worksheet.merge_range('A1:F1', '')
        company = self.env.user.company_id

        # Get the logged-in user's name
        user = request.env.user
        user_name = user.name
        email = user.login
        job_position = ''
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id), ('job_id', '!=', False)],
                                                            limit=1)
        if employee:
            job_position = employee.job_id.name or ''

        # Find the department name of the employee
        department_name = ''
        if employee and employee.department_id:
            department_name = employee.department_id.name or ''

        company_info = "\n".join(filter(None, [company.name, company.street2, company.street, company.city,
                                               company.country_id.name,
                                               'Phone: ' + company.phone + ' Email: ' + company.email + ' Web: ' + company.website]))
        worksheet.merge_range('A1:I1', company_info, heading_format)

        # Convert the logo from base64 to binary data
        logo_data = base64.b64decode(company.logo)

        # Create a BytesIO object to hold the image data
        image_stream = BytesIO(logo_data)
        # Add the logo to the worksheet
        worksheet.insert_image('F1', 'logo.png', {'image_data': image_stream, 'x_scale': 0.43, 'y_scale': 0.43})

        worksheet.set_row(1, 26)
        worksheet.merge_range('A2:I2', 'ASSET REPORT', title_format)

        worksheet.set_row(2, 12)
        worksheet.set_column('A:A', 9)
        worksheet.set_column('B:G', 20)
        worksheet.set_column('H:I', 11)
        worksheet.set_column('H8:H8', 19)
        worksheet.set_row(6, 12)
        worksheet.merge_range('A3:I3', '', divider_format)
        worksheet.merge_range('A7:I7', '', divider_format)

        worksheet.write('A4:A4', 'Extracted by', cell_text_info_format)
        worksheet.merge_range('B4:D4', user_name, cell_text_info_body_format)

        worksheet.write('A5:A5', 'Date', cell_text_info_format)
        worksheet.merge_range('B5:I5', datetime.now().strftime('%m-%d-%Y'), cell_text_info_body_format)

        worksheet.write('A6:A6', 'Email', cell_text_info_format)
        worksheet.merge_range('B6:D6', email, cell_text_info_body_format)

        worksheet.write('E4:E4', 'Designation', cell_text_info_format)
        worksheet.merge_range('F4:I4', job_position, cell_text_info_body_format)

        worksheet.write('E6:E6', 'Department', cell_text_info_format)
        worksheet.merge_range('F6:I6', department_name, cell_text_info_body_format)

        worksheet.write('A8:A8', 'S/N', cell_text_sub_title_format)
        worksheet.write('B8:B8', 'Asset Name', cell_text_sub_title_format)
        worksheet.write('C8:C8', 'S/N/Asset ID', cell_text_sub_title_format)
        worksheet.write('D8:D8', 'Asset No', cell_text_sub_title_format)
        worksheet.write('E8:E8', 'Date', cell_text_sub_title_format)
        worksheet.write('F8:F8', 'Amount', cell_text_sub_title_format)
        worksheet.write('G8:G8', 'Assigned To', cell_text_sub_title_format)
        worksheet.write('H8:H8', 'Department', cell_text_sub_title_format)
        worksheet.write('I8:I8', 'Status', cell_text_sub_title_format)

        department_asset = self.env['account.asset.asset'].sudo().search(
            [('department_id', '=', self.department_name), ('date', '<=', self.date_to)])

        # all_asset = self.env['account.asset.asset'].sudo().search([])
        all_asset = self.env['account.asset.asset'].sudo().search([('date', '<=', self.date_to)])

        row = 8
        col = 0
        index = 1

        if department_asset:
            for asset in department_asset:
                index = index
                asset_name = asset.name
                asset_id = asset.asset_id_no
                asset_number = asset.code
                purchase_date = datetime.strftime(asset.date, '%d-%m-%Y')
                amount = asset.value
                assigned_to = 'Null'
                department = asset.department_id.name
                status = asset.state

                worksheet.write(row, col, index or '', cell_text_body_format)
                worksheet.write(row, col + 1, asset_name or '', cell_text_body_format)
                worksheet.write(row, col + 2, asset_id or '', cell_text_body_format)
                worksheet.write(row, col + 3, asset_number or '', cell_text_body_format)
                worksheet.write(row, col + 4, purchase_date or '', cell_text_body_format)
                worksheet.write(row, col + 5, amount or '', cell_text_body_format)
                worksheet.write(row, col + 6, assigned_to or '', cell_text_body_format)
                worksheet.write(row, col + 7, department or '', cell_text_body_format)
                worksheet.write(row, col + 8, status or '', cell_text_body_format)

                row = row + 1
                index = index + 1
        else:
            for asset in all_asset:
                index = index
                asset_name = asset.name
                asset_id = asset.asset_id_no
                asset_number = asset.code
                purchase_date = datetime.strftime(asset.date, '%d-%m-%Y')
                amount = asset.value
                assigned_to = 'Null'
                department = asset.department_id.name
                status = asset.state

                worksheet.write(row, col, index or '', cell_text_body_format)
                worksheet.write(row, col + 1, asset_name or '', cell_text_body_format)
                worksheet.write(row, col + 2, asset_id or '', cell_text_body_format)
                worksheet.write(row, col + 3, asset_number or '', cell_text_body_format)
                worksheet.write(row, col + 4, purchase_date or '', cell_text_body_format)
                worksheet.write(row, col + 5, amount or '', cell_text_body_format)
                worksheet.write(row, col + 6, assigned_to or '', cell_text_body_format)
                worksheet.write(row, col + 7, department or '', cell_text_body_format)
                worksheet.write(row, col + 8, status or '', cell_text_body_format)

                row = row + 1
                index = index + 1

        workbook.close()
        file_download = base64.b64encode(fp.getvalue())
        fp.close()

        self = self.with_context(default_name=file_name, default_file_download=file_download)

        return {
            'name': 'Asset Report Download',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'asset.list.excel',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': self._context,
        }


class AssetListReportExcel(models.TransientModel):
    _name = 'asset.list.excel'
    _description = "Asset List excel table"

    name = fields.Char('File Name', size=256, readonly=True)
    file_download = fields.Binary('Download Asset', readonly=True)


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
        ("reject", "Reject"),
    ]

    def _default_assignment(self):
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        if employee:
            return employee.id

    date_created = fields.Date('Date / Time', readonly=True, required=True, index=True,
                               default=fields.date.today(), store=True)
    attachment = fields.Binary(string="Attachment", attachment=True, store=True, )
    attachment_name = fields.Char('Attachment Name')
    assignment_no = fields.Char('Assignment No', readonly=True, store=True)
    assigned_by = fields.Many2one('res.users', 'Assigned By', default=lambda self: self.env.uid, readonly=True)
    assigned_person = fields.Many2one('hr.employee', 'Assigned Person', default=_default_assignment)
    department_id = fields.Char('Department', related='assigned_person.department_id.name')
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

    def get_custodian_report(self):
        return self.env.ref('asset_management.asset_custodian_report_excel').report_action(self)

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
    def button_line_manager_reject(self):
        for asset in self.asset_ids:
            asset.write({'close': True})
        self.write({'state': 'reject'})
        return True

    @api.multi
    def button_line_manager_back_to_draft(self):
        self.write({'state': 'draft'})
        return True

    @api.multi
    def button_line_manager_review(self):
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
    def button_procurement_back_to_line_manager(self):
        self.write({'state': 'send_request'})
        return True

    @api.multi
    def button_procurement_reject(self):
        self.write({'state': 'reject'})
        return True

    @api.multi
    def button_assign(self):
        for asset in self.asset_ids:
            asset.write({'assigned': True})
        self.write({'state': 'assigned'})
        return True

    @api.multi
    def button_back_to_procurement(self):
        self.write({'state': 'line_manager'})
        return True

    @api.multi
    def button_procurement_reject(self):
        self.write({'state': 'reject'})
        return True

    @api.multi
    def button_unassign(self):
        for asset in self.asset_ids:
            asset.write({'assigned': False})
        self.write({'state': 'unassigned'})
        return True


class AssetSupportDocumentLines(models.Model):
    _name = 'account.asset.support.document.line'

    document_name = fields.Char(string="Document Name")
    attachment = fields.Binary(string="Attachment", attachment=True, store=True, )
    attachment_name = fields.Char('Attachment Name')
    document_ids = fields.Many2one('account.asset.asset', string="Document ID")


class InsuranceModelsLines(models.Model):
    _name = 'insurance.model.line'

    name = fields.Char(string="Name")
    date = fields.Date(string="Date")
    expire_date = fields.Date(string="Expire Date")
    insurance_ids = fields.Many2one('account.asset.asset', string="Insurance ID")


class ServicesModelLines(models.Model):
    _name = 'service.model.line'

    service_date = fields.Date(string="Service Date")
    next_service = fields.Date(string="Next Service")
    service_ids = fields.Many2one('account.asset.asset', string="Service ID")


class DescriptionsLines(models.Model):
    _name = 'description.line'

    title = fields.Char(string="Title")
    description = fields.Char(string="Description")
    description_ids = fields.Many2one('account.asset.asset', string="Description ID")


class AssetAssignmentCategory(models.Model):
    _name = 'account.asset.assign.category.line'

    name = fields.Many2one('account.asset.category', string='Asset')
    asset_name = fields.Char(string='Specify Asset')
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
