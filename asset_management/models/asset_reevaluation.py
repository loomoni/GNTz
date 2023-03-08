from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero
import calendar
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

class AssetReevaluation(models.Model):
    _name = 'account.asset.reevaluation'
    _rec_name = 'name'
    _description = "Asset Re-evaluation"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    def _default_reserve_account(self):
        account = self.env['account.account'].search(
            [('name', 'like', 'Revaluation')], limit=1)
        if account is not None:
            return account.id

    def _default_reserve_journal(self):
        journal = self.env['account.journal'].search(
            [('name', 'like', 'Asset')], limit=1)
        if journal is not None:
            return journal.id

    STATE_SELECTION = [
        ("draft", "Draft"),
        ("fm_approved", "FM Approved"),
        ("asset_evaluated", "Asset Evaluated"),
        ("md_approved", "MD Approved"),
        ("asset_reevaluated", "Asset Reevaluated"),
        ("rejected", "Rejected"),
    ]

    date_created = fields.Date('Date / Time', readonly=True, required=True, index=True,
                               default=fields.Date.context_today, store=True)
    name = fields.Char(string='Reference',required=True)
    state = fields.Selection(STATE_SELECTION, index=True, track_visibility='onchange', required=True, copy=False,
                             default='draft')
    asset_id = fields.Many2one('account.asset.asset', string='Asset', required=True, domain=[('state','=','open')])
    original_value = fields.Float(string='Original Asset Value')
    evaluated_value = fields.Float(string='Evaluated Asset Value')
    account_id = fields.Many2one('account.account', string='Revaluation Reserve Account', required=True, default=_default_reserve_account)
    journal_id = fields.Many2one('account.journal', string='Revaluation Account Journal', required=True, default=_default_reserve_journal)
    move_id = fields.Many2one('account.move', string='Revaluation Entry')
    line_ids = fields.One2many('account.asset.reevaluation.depreciation.lines', 'reevaluation_id', string='Asset Depreciation Lines', store=True)

    @api.onchange('asset_id')
    def onchange_asset_id(self):
        totalDepreciated = 0
        for depreciation in self.asset_id.depreciation_line_ids:
            if depreciation.move_check is True:
                totalDepreciated += depreciation.amount
        self.original_value = self.asset_id.value - totalDepreciated

    @api.multi
    def button_reject(self):
        self.write({'state': 'rejected'})
        return True

    @api.multi
    def button_fm_approve(self):
        self.write({'state': 'fm_approved'})
        return True

    @api.multi
    def button_evaluate(self):
        evaluatedAmount = self.evaluated_value
        if self.evaluated_value != 0.0:
            amount_to_depr = self.evaluated_value
            posted_depreciation_line_ids = self.asset_id.depreciation_line_ids.filtered(lambda x: x.move_check).sorted(
                key=lambda l: l.depreciation_date)

            if posted_depreciation_line_ids and posted_depreciation_line_ids[-1].depreciation_date:
                last_depreciation_date = fields.Date.from_string(posted_depreciation_line_ids[-1].depreciation_date)
                depreciation_date = last_depreciation_date + relativedelta(months=+self.asset_id.method_period)
            else:
                # depreciation_date computed from the purchase date
                depreciation_date = self.date_created
                if self.asset_id.date_first_depreciation == 'last_day_period':
                    # depreciation_date = the last day of the month
                    depreciation_date = depreciation_date + relativedelta(day=31)
                    # ... or fiscalyear depending the number of period
                    if self.asset_id.method_period == 12:
                        depreciation_date = depreciation_date + relativedelta(
                            month=self.asset_id.company_id.fiscalyear_last_month)
                        depreciation_date = depreciation_date + relativedelta(day=self.asset_id.company_id.fiscalyear_last_day)
                        if depreciation_date < self.date_created:
                            depreciation_date = depreciation_date + relativedelta(years=1)
                elif self.asset_id.first_depreciation_manual_date and self.asset_id.first_depreciation_manual_date != self.date_created:
                    # depreciation_date set manually from the 'first_depreciation_manual_date' field
                    depreciation_date = self.asset_id.first_depreciation_manual_date


            total_days = (depreciation_date.year % 4) and 365 or 366
            month_day = depreciation_date.day
            undone_dotation_number = self._compute_board_undone_dotation_nb(depreciation_date, total_days)

            amountDepreciated = 0
            commands = []
            for x in range(len(posted_depreciation_line_ids), undone_dotation_number):
                sequence = x + 1
                amount = self._compute_board_amount(sequence, self.evaluated_value, amount_to_depr, undone_dotation_number, posted_depreciation_line_ids, total_days, depreciation_date)
                amount = self.asset_id.currency_id.round(amount)
                if float_is_zero(amount, precision_rounding=self.asset_id.currency_id.rounding):
                    continue
                self.evaluated_value -= amount
                amountDepreciated += amount
                vals = {
                    'amount': amount,
                    'asset_id': self.asset_id.id,
                    'sequence': sequence,
                    'name': (self.asset_id.code or '') + '/' + str(sequence),
                    'remaining_value': self.evaluated_value,
                    'depreciated_value': amountDepreciated,
                    'depreciation_date': depreciation_date,
                }
                commands.append((0, False, vals))

                depreciation_date = depreciation_date + relativedelta(months=+self.asset_id.method_period)

                if month_day > 28 and self.asset_id.date_first_depreciation == 'manual':
                    max_day_in_month = calendar.monthrange(depreciation_date.year, depreciation_date.month)[1]
                    depreciation_date = depreciation_date.replace(day=min(max_day_in_month, month_day))

                # datetime doesn't take into account that the number of days is not the same for each month
                if not self.asset_id.prorata and self.asset_id.method_period % 12 != 0 and self.asset_id.date_first_depreciation == 'last_day_period':
                    max_day_in_month = calendar.monthrange(depreciation_date.year, depreciation_date.month)[1]
                    depreciation_date = depreciation_date.replace(day=max_day_in_month)

            self.write({'line_ids': commands})
            self.write({'evaluated_value': evaluatedAmount})
        self.write({'state': 'asset_evaluated'})
        return True

    @api.multi
    def button_md_approve(self):
        self.write({'state': 'md_approved'})
        return True

    @api.multi
    def button_reevaluate(self):
        # handle account moves for reevaluation for assets
        created_moves = self.env['account.move']
        category_id = self.asset_id.category_id
        account_analytic_id = self.asset_id.account_analytic_id
        analytic_tag_ids = self.asset_id.analytic_tag_ids
        depreciation_date = fields.Date.context_today(self)
        company_currency = self.asset_id.company_id.currency_id
        current_currency = self.asset_id.currency_id
        prec = company_currency.decimal_places
        asset_name = self.asset_id.name + ' (%s)' % (len(self.asset_id.depreciation_line_ids))
        unposted_depreciation_line_ids = self.asset_id.depreciation_line_ids.filtered(lambda x: not x.move_check)
        if unposted_depreciation_line_ids:
            old_values = {
                'method_end': self.asset_id.method_end,
                'method_number': self.asset_id.method_number,
            }

            # Remove all unposted depr. lines
            commands = [(2, line_id.id, False) for line_id in unposted_depreciation_line_ids]

            # Create a new depr lines. self with the new evaluated amount and post it
            today = fields.Datetime.today()
            sequence = len(self.asset_id.depreciation_line_ids) - len(unposted_depreciation_line_ids) + 1
            for line in self.line_ids:
                vals = {
                    'amount': line.amount,
                    'asset_id': line.asset_id.id,
                    'sequence': line.sequence,
                    'name': line.name,
                    'remaining_value': line.remaining_value,
                    'depreciated_value': line.depreciated_value,  # the asset is completely depreciated
                    'depreciation_date': line.depreciation_date,
                }
                commands.append((0, False, vals))
                sequence += 1
            self.asset_id.write({'depreciation_line_ids': commands, 'method_end': today, 'method_number': sequence})
            tracked_fields = self.env['account.asset.asset'].fields_get(['method_number', 'method_end'])
            changes, tracking_value_ids = self.asset_id._message_track(tracked_fields, old_values)
            if changes:
                self.asset_id.message_post(
                    subject=_('Asset has been reevaluated'),
                    tracking_value_ids=tracking_value_ids)

            if self.evaluated_value > self.original_value:
                amount = self.evaluated_value - self.original_value
                move_line_1 = {
                    'name': asset_name,
                    'account_id':  category_id.account_asset_id.id,
                    'credit': 0.0,
                    'debit': amount,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and amount or 0.0,
                }
                move_line_2 = {
                    'name': asset_name,
                    'account_id': self.account_id.id,
                    'debit': 0.0,
                    'credit': amount,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and - 1.0 * amount or 0.0,
                }

                move_vals = {
                    'ref': self.asset_id.code,
                    'date': depreciation_date or False,
                    'journal_id': self.journal_id.id,
                    'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
                }
                move = self.env['account.move'].create(move_vals)
                self.write({'move_id': move.id})
            elif self.evaluated_value < self.original_value:
                amount = self.original_value - self.evaluated_value
                move_line_1 = {
                    'name': asset_name,
                    'account_id': category_id.account_asset_id.id,
                    'credit': amount,
                    'debit': 0.0,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and amount or 0.0,
                }
                move_line_2 = {
                    'name': asset_name,
                    'account_id': self.account_id.id,
                    'debit': amount,
                    'credit': 0.0,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and - 1.0 * amount or 0.0,
                }

                move_vals = {
                    'ref': self.asset_id.code,
                    'date': depreciation_date or False,
                    'journal_id': self.journal_id.id,
                    'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
                }
                move = self.env['account.move'].create(move_vals)
                self.write({'move_id': move.id})

        self.write({'state': 'asset_reevaluated'})
        self.asset_id.write({'value': self.evaluated_value})
        return True

    def _compute_board_undone_dotation_nb(self, depreciation_date, total_days):
        undone_dotation_number = self.asset_id.method_number
        if self.asset_id.method_time == 'end':
            end_date = self.asset_id.method_end
            undone_dotation_number = 0
            while depreciation_date <= end_date:
                depreciation_date = date(depreciation_date.year, depreciation_date.month,
                                         depreciation_date.day) + relativedelta(months=+self.asset_id.method_period)
                undone_dotation_number += 1
        if self.asset_id.prorata:
            undone_dotation_number += 1
        return undone_dotation_number

    def _compute_board_amount(self, sequence, residual_amount, amount_to_depr, undone_dotation_number,
                              posted_depreciation_line_ids, total_days, depreciation_date):
        amount = 0
        if sequence == undone_dotation_number:
            amount = residual_amount
        else:
            if self.asset_id.method == 'linear':
                amount = amount_to_depr / (undone_dotation_number - len(posted_depreciation_line_ids))
                if self.asset_id.prorata:
                    amount = amount_to_depr / self.asset_id.method_number
                    if sequence == 1:
                        date = self.asset_id.date
                        if self.asset_id.method_period % 12 != 0:
                            month_days = calendar.monthrange(date.year, date.month)[1]
                            days = month_days - date.day + 1
                            amount = (amount_to_depr / self.asset_id.method_number) / month_days * days
                        else:
                            days = (self.asset_id.company_id.compute_fiscalyear_dates(date)['date_to'] - date).days + 1
                            amount = (amount_to_depr / self.asset_id.method_number) / total_days * days
            elif self.asset_id.method == 'degressive':
                amount = residual_amount * self.asset_id.method_progress_factor
                if self.asset_id.prorata:
                    if sequence == 1:
                        date = self.asset_id.date
                        if self.asset_id.method_period % 12 != 0:
                            month_days = calendar.monthrange(date.year, date.month)[1]
                            days = month_days - date.day + 1
                            amount = (residual_amount * self.asset_id.method_progress_factor) / month_days * days
                        else:
                            days = (self.asset_id.company_id.compute_fiscalyear_dates(date)['date_to'] - date).days + 1
                            amount = (residual_amount * self.asset_id.method_progress_factor) / total_days * days
        return amount


class AssetReevaluationDepreciationLines(models.Model):
    _name = 'account.asset.reevaluation.depreciation.lines'
    _description = "Asset Re-evaluation Theoretical Depreciation"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    reevaluation_id = fields.Many2one('account.asset.reevaluation', string='Asset Reevaluation', index=True, readonly=True,
                                  store=True)
    name = fields.Char(string='Depreciation Name', required=True, index=True)
    sequence = fields.Integer(required=True)
    asset_id = fields.Many2one('account.asset.asset', string='Asset', required=True, ondelete='cascade')
    parent_state = fields.Selection(related='asset_id.state', string='State of Asset')
    reason_for_disposal = fields.Text(string='Reason for Disposal')
    amount = fields.Float(string='Current Depreciation', digits=0, required=True)
    remaining_value = fields.Float(string='Next Period Depreciation', digits=0, required=True)
    depreciated_value = fields.Float(string='Cumulative Depreciation', required=True)
    depreciation_date = fields.Date('Depreciation Date', index=True)
