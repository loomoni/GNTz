from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero


class AssetDisposal(models.Model):
    _name = 'account.asset.disposal'
    _rec_name = 'name'
    _description = "Asset Disposal"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # STATE_SELECTION = [
    #     ("draft", "Draft"),
    #     ("fm_approved", "Procurement Approved"),
    #     ("asset_evaluation", "Asset Evaluation"),
    #     ("asset_evaluated", "Asset Evaluated"),
    #     ("md_approved", "AD Manager/CD Approved"),
    #     ("asset_disposed", "Asset Disposed"),
    #     ("rejected", "Rejected"),
    # ]

    STATE_SELECTION = [
        ("draft", "Draft"),
        ("procurement_evaluate", "Procurement Evaluate"),
        ("ad_manager_approve", "AD Manager/ Country Director Approve "),
        ("rejected", "Rejected"),
    ]

    def _default_loss_gain_account(self):
        lossgain = self.env['account.account'].search(
            [('name', 'like', 'Gain/Loss of Asset Disposal')], limit=1)
        if lossgain is not None:
            return lossgain.id

    date_created = fields.Date('Date / Time', readonly=True, required=True, index=True,
                               default=fields.date.today(), store=True)
    name = fields.Char(string='Reference', required=True)
    state = fields.Selection(STATE_SELECTION, index=True, track_visibility='onchange', required=True, copy=False,
                             default='draft')
    account_id = fields.Many2one('account.account', string='Gain/Loss on Sale of Asset Account', required=True,
                                 default=_default_loss_gain_account)
    line_ids = fields.One2many('account.asset.disposal.lines', 'disposal_id', string='Asset Disposal Lines', store=True)
    total_disposal_amount = fields.Float(string='Total Disposal Amount', compute='_compute_total_disposal_amount')
    evaluation_report = fields.Binary(attachment=True, store=True, string='Upload Asset Evaluation Report')
    evaluation_report_file_name = fields.Char('Evaluation Report File Name')

    @api.depends('line_ids', 'line_ids.evaluated_disposal_amount')
    def _compute_total_disposal_amount(self):
        for rec in self:
            for line in rec.line_ids:
                rec.total_disposal_amount += line.evaluated_disposal_amount

    @api.multi
    def button_reject(self):
        self.write({'state': 'rejected'})
        return True

    @api.multi
    def button_fm_approve(self):
        self.write({'state': 'fm_approved'})
        for lin in self.line_ids:
            lin.write({'check_evaluation': True})
        checkEvaluation = False
        for line in self.line_ids:
            if line.original_disposal_amount > 500:
                checkEvaluation = True
                break
        if checkEvaluation is True:
            self.write({'state': 'asset_evaluation'})
        else:
            self.write({'state': 'asset_evaluated'})
        return True



    @api.multi
    def button_md_approve(self):
        self.write({'state': 'md_approved'})
        return True

    @api.multi
    def button_procurement_evaluate(self):
        self.write({'state': 'procurement_evaluate'})
        return True

    @api.multi
    def button_dispose(self):
        # handle account moves for disposal and active false for disposed assets
        created_moves = self.env['account.move']
        for line in self.line_ids:
            category_id = line.asset_id.category_id
            account_analytic_id = line.asset_id.account_analytic_id
            analytic_tag_ids = line.asset_id.analytic_tag_ids
            depreciation_date = fields.Date.context_today(self)
            company_currency = line.asset_id.company_id.currency_id
            current_currency = line.asset_id.currency_id
            prec = company_currency.decimal_places
            amount = current_currency._convert(
                line.evaluated_disposal_amount, company_currency, line.asset_id.company_id, depreciation_date)
            asset_name = line.asset_id.name + ' (%s)' % (len(line.asset_id.depreciation_line_ids))
            if line.disposal_type == "dispose":
                unposted_depreciation_line_ids = line.asset_id.depreciation_line_ids.filtered(
                    lambda x: not x.move_check)
                if unposted_depreciation_line_ids:
                    old_values = {
                        'method_end': line.asset_id.method_end,
                        'method_number': line.asset_id.method_number,
                    }

                    # Remove all unposted depr. lines
                    commands = [(2, line_id.id, False) for line_id in unposted_depreciation_line_ids]

                    # Create a new depr. line with the residual amount and post it
                    sequence = len(line.asset_id.depreciation_line_ids) - len(unposted_depreciation_line_ids) + 1
                    today = fields.Datetime.today()
                    vals = {
                        'amount': line.evaluated_disposal_amount,
                        'asset_id': line.asset_id.id,
                        'sequence': sequence,
                        'name': (line.asset_id.code or '') + '/' + str(sequence),
                        'remaining_value': 0,
                        'depreciated_value': line.evaluated_disposal_amount,  # the asset is completely depreciated
                        'depreciation_date': today,
                    }
                    commands.append((0, False, vals))
                    line.asset_id.write(
                        {'depreciation_line_ids': commands, 'method_end': today, 'method_number': sequence})
                    tracked_fields = self.env['account.asset.asset'].fields_get(['method_number', 'method_end'])
                    changes, tracking_value_ids = line.asset_id._message_track(tracked_fields, old_values)
                    if changes:
                        line.asset_id.message_post(
                            subject=_('Asset sold or disposed. Accounting entry awaiting for validation.'),
                            tracking_value_ids=tracking_value_ids)

                move_line_1 = {
                    'name': asset_name,
                    'account_id': category_id.account_depreciation_id.id,
                    'debit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
                    'credit': amount if float_compare(amount, 0.0, precision_digits=prec) > 0 else 0.0,
                    'partner_id': line.asset_id.partner_id.id,
                    'analytic_account_id': account_analytic_id.id if category_id.type == 'sale' else False,
                    'analytic_tag_ids': [(6, 0, analytic_tag_ids.ids)] if category_id.type == 'sale' else False,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and - 1.0 * line.amount or 0.0,
                }
                move_line_2 = {
                    'name': asset_name,
                    'account_id': category_id.account_depreciation_expense_id.id,
                    'credit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
                    'debit': amount if float_compare(amount, 0.0, precision_digits=prec) > 0 else 0.0,
                    'partner_id': line.asset_id.partner_id.id,
                    'analytic_account_id': account_analytic_id.id if category_id.type == 'purchase' else False,
                    'analytic_tag_ids': [(6, 0, analytic_tag_ids.ids)] if category_id.type == 'purchase' else False,
                    'currency_id': company_currency != current_currency and current_currency.id or False,
                    'amount_currency': company_currency != current_currency and line.amount or 0.0,
                }
                move_vals = {
                    'ref': line.asset_id.code,
                    'date': depreciation_date or False,
                    'journal_id': category_id.journal_id.id,
                    'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
                }
                move = self.env['account.move'].create(move_vals)
                line.write({'move_id': move.id})
            else:
                unposted_depreciation_line_ids = line.asset_id.depreciation_line_ids.filtered(
                    lambda x: not x.move_check)
                if unposted_depreciation_line_ids:
                    old_values = {
                        'method_end': line.asset_id.method_end,
                        'method_number': line.asset_id.method_number,
                    }

                    # Remove all unposted depr. lines
                    commands = [(2, line_id.id, False) for line_id in unposted_depreciation_line_ids]
                    sequence = len(line.asset_id.depreciation_line_ids) - len(unposted_depreciation_line_ids) + 1
                    today = fields.Datetime.today()
                    line.asset_id.write(
                        {'depreciation_line_ids': commands, 'method_end': today, 'method_number': sequence})
                if line.evaluated_disposal_amount > line.original_disposal_amount:
                    profit = line.evaluated_disposal_amount - line.original_disposal_amount
                    move_line_1 = {
                        'name': asset_name,
                        'account_id': line.account_id.id,
                        'credit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
                        'debit': amount if float_compare(amount, 0.0, precision_digits=prec) > 0 else 0.0,
                        'partner_id': line.partner_id.id if line.partner_id else False,
                        'analytic_account_id': account_analytic_id.id if category_id.type == 'purchase' else False,
                        'analytic_tag_ids': [(6, 0, analytic_tag_ids.ids)] if category_id.type == 'purchase' else False,
                        'currency_id': company_currency != current_currency and current_currency.id or False,
                        'amount_currency': company_currency != current_currency and line.amount or 0.0,
                    }
                    move_line_2 = {
                        'name': asset_name,
                        'account_id': self.account_id.id,
                        'debit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
                        'credit': profit if float_compare(amount, 0.0, precision_digits=prec) > 0 else 0.0,
                        'partner_id': line.partner_id.id if line.partner_id else False,
                        'analytic_account_id': account_analytic_id.id if category_id.type == 'sale' else False,
                        'analytic_tag_ids': [(6, 0, analytic_tag_ids.ids)] if category_id.type == 'sale' else False,
                        'currency_id': company_currency != current_currency and current_currency.id or False,
                        'amount_currency': company_currency != current_currency and - 1.0 * line.amount or 0.0,
                    }
                    move_line_3 = {
                        'name': asset_name,
                        'account_id': category_id.account_asset_id.id,
                        'debit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
                        'credit': line.original_disposal_amount if float_compare(amount, 0.0,
                                                                                 precision_digits=prec) > 0 else 0.0,
                        'partner_id': line.partner_id.id if line.partner_id else False,
                        'analytic_account_id': account_analytic_id.id if category_id.type == 'sale' else False,
                        'analytic_tag_ids': [(6, 0, analytic_tag_ids.ids)] if category_id.type == 'sale' else False,
                        'currency_id': company_currency != current_currency and current_currency.id or False,
                        'amount_currency': company_currency != current_currency and - 1.0 * line.amount or 0.0,
                    }

                    move_vals = {
                        'ref': line.asset_id.code,
                        'date': depreciation_date or False,
                        'journal_id': line.journal_id.id,
                        'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2), (0, 0, move_line_3)],
                    }
                    move = self.env['account.move'].create(move_vals)
                    line.write({'move_id': move.id})
                elif line.evaluated_disposal_amount < line.original_disposal_amount:
                    loss = line.original_disposal_amount - line.evaluated_disposal_amount
                    move_line_1 = {
                        'name': asset_name,
                        'account_id': line.account_id.id,
                        'credit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
                        'debit': line.evaluated_disposal_amount if float_compare(amount, 0.0,
                                                                                 precision_digits=prec) > 0 else 0.0,
                        'partner_id': line.partner_id.id if line.partner_id else False,
                        'analytic_account_id': account_analytic_id.id if category_id.type == 'purchase' else False,
                        'analytic_tag_ids': [(6, 0, analytic_tag_ids.ids)] if category_id.type == 'purchase' else False,
                        'currency_id': company_currency != current_currency and current_currency.id or False,
                        'amount_currency': company_currency != current_currency and line.amount or 0.0,
                    }
                    move_line_2 = {
                        'name': asset_name,
                        'account_id': self.account_id.id,
                        'credit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
                        'debit': loss if float_compare(amount, 0.0,
                                                       precision_digits=prec) > 0 else 0.0,
                        'partner_id': line.partner_id.id if line.partner_id else False,
                        'analytic_account_id': account_analytic_id.id if category_id.type == 'purchase' else False,
                        'analytic_tag_ids': [(6, 0, analytic_tag_ids.ids)] if category_id.type == 'purchase' else False,
                        'currency_id': company_currency != current_currency and current_currency.id or False,
                        'amount_currency': company_currency != current_currency and line.amount or 0.0,
                    }
                    move_line_3 = {
                        'name': asset_name,
                        'account_id': category_id.account_asset_id.id,
                        'debit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
                        'credit': line.original_disposal_amount if float_compare(amount, 0.0,
                                                                                 precision_digits=prec) > 0 else 0.0,
                        'partner_id': line.partner_id.id if line.partner_id else False,
                        'analytic_account_id': account_analytic_id.id if category_id.type == 'sale' else False,
                        'analytic_tag_ids': [(6, 0, analytic_tag_ids.ids)] if category_id.type == 'sale' else False,
                        'currency_id': company_currency != current_currency and current_currency.id or False,
                        'amount_currency': company_currency != current_currency and - 1.0 * line.amount or 0.0,
                    }

                    move_vals = {
                        'ref': line.asset_id.code,
                        'date': depreciation_date or False,
                        'journal_id': line.journal_id.id,
                        'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2), (0, 0, move_line_3)],
                    }
                    move = self.env['account.move'].create(move_vals)
                    line.write({'move_id': move.id})
                else:
                    move_line_1 = {
                        'name': asset_name,
                        'account_id': category_id.account_asset_id.id,
                        'debit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
                        'credit': amount if float_compare(amount, 0.0, precision_digits=prec) > 0 else 0.0,
                        'partner_id': line.partner_id.id if line.partner_id else False,
                        'analytic_account_id': account_analytic_id.id if category_id.type == 'sale' else False,
                        'analytic_tag_ids': [(6, 0, analytic_tag_ids.ids)] if category_id.type == 'sale' else False,
                        'currency_id': company_currency != current_currency and current_currency.id or False,
                        'amount_currency': company_currency != current_currency and - 1.0 * line.amount or 0.0,
                    }
                    move_line_2 = {
                        'name': asset_name,
                        'account_id': line.account_id.id,
                        'credit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
                        'debit': amount if float_compare(amount, 0.0, precision_digits=prec) > 0 else 0.0,
                        'partner_id': line.partner_id.id if line.partner_id else False,
                        'analytic_account_id': account_analytic_id.id if category_id.type == 'purchase' else False,
                        'analytic_tag_ids': [(6, 0, analytic_tag_ids.ids)] if category_id.type == 'purchase' else False,
                        'currency_id': company_currency != current_currency and current_currency.id or False,
                        'amount_currency': company_currency != current_currency and line.amount or 0.0,
                    }
                    move_vals = {
                        'ref': line.asset_id.code,
                        'date': depreciation_date or False,
                        'journal_id': line.journal_id.id,
                        'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
                    }
                    move = self.env['account.move'].create(move_vals)
                    line.write({'move_id': move.id})

            line.asset_id.write({'state': 'close'})
        self.write({'state': 'ad_manager_approve'})
        return True


class AssetDisposalLines(models.Model):
    _name = 'account.asset.disposal.lines'
    _rec_name = 'asset_id'
    _description = "Disposal Lines"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    DISPOSAL_TYPE = [
        ("sell", "SELL"),
        ("donation", "Donation"),
        ("transfer", "Transfer"),
        ("dispose", "DISPOSE"),
    ]

    disposal_id = fields.Many2one('account.asset.disposal', string='Asset Disposal', index=True, readonly=True,
                                  store=True)
    asset_id = fields.Many2one('account.asset.asset', string='Asset', required=True, domain=[('state', '=', 'open')])
    disposal_type = fields.Selection(DISPOSAL_TYPE, index=True, track_visibility='onchange', required=True, copy=False,
                                     default='sell')
    original_disposal_amount = fields.Float(string='Original Disposal Amount')
    reason_for_disposal = fields.Text(string='Reason for Disposal')
    evaluated_disposal_amount = fields.Float(string='Evaluated Disposal Amount')
    partner_id = fields.Many2one('res.partner', string='Sold To')
    move_id = fields.Many2one('account.move', string='Disposal Entry')
    account_id = fields.Many2one('account.account', string='Debit Account', required=True)
    journal_id = fields.Many2one('account.journal', string='Disposal Journal', required=True)
    check_evaluation = fields.Boolean(default=False)

    @api.onchange('asset_id')
    def onchange_asset_id(self):
        totalDepreciated = 0
        for depreciation in self.asset_id.depreciation_line_ids:
            if depreciation.move_check is True:
                totalDepreciated += depreciation.amount
        self.original_disposal_amount = self.asset_id.value - totalDepreciated
        if self.original_disposal_amount <= 500:
            self.evaluated_disposal_amount = self.original_disposal_amount

    @api.onchange('asset_id', 'disposal_type')
    def onchange_asset_id_disposal_type(self):
        if self.asset_id and self.disposal_type == 'dispose':
            self.account_id = self.asset_id.category_id.account_depreciation_expense_id.id
            self.journal_id = self.asset_id.category_id.journal_id.id
            self.evaluated_disposal_amount = self.original_disposal_amount
        if self.asset_id and self.disposal_type == 'sell':
            debitAcc = self.env['account.account'].search(
                [('name', 'like', 'Bank')], limit=1)
            if debitAcc is not None:
                self.account_id = debitAcc.id

            debitJournal = self.env['account.journal'].search(
                [('name', 'like', 'Asset')], limit=1)
            if debitJournal is not None:
                self.journal_id = debitJournal.id
