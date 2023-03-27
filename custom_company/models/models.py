# -*- coding: utf-8 -*-

from odoo import models, fields, api


class CompanyBranches(models.Model):
    _name = "hr.branches"
    _description = "Company Branches"
    _inherit = ['mail.thread']
    _order = "code"

    name = fields.Char('Branch Name', required=True)
    image_small = fields.Binary(
        "Small-sized image", attachment=True)
    code = fields.Char('Branch Code', required=True)
    main_branch = fields.Boolean('HQ Branch', default=False)
    manager_id = fields.Many2many('hr.employee', string='Procurement Team', track_visibility='onchange')
    accountant_id = fields.Many2many('res.users', string='Finance Team', track_visibility='onchange')
    ict_officer_id = fields.Many2one('hr.employee', string='ICT Officer', track_visibility='onchange')
    hr_manager_id = fields.Many2one('hr.employee', string='Branch HR', track_visibility='onchange')
    cashier_id = fields.Many2one('hr.employee', string='Branch Cashier', track_visibility='onchange')


class HRDepartmentInherit(models.Model):
    _inherit = "hr.department"

    def _default_code(self):
        deptList = self.env['hr.department'].sudo().search_count([])
        return str(deptList + 1)

    branch_id = fields.Many2one('hr.branches', string='Branch', required=True)
    code = fields.Char('Department Code', required=True, default=_default_code)


class HREmployeesInherit(models.Model):
    _inherit = "hr.employee"

    department_parent_id = fields.Many2one(comodel_name='hr.department', string='Parent Department', required=True)
    is_po = fields.Boolean(string='Is Purchase Officer', default=False)
    is_fm = fields.Boolean(string='Is Finance Manager', default=False)
    is_md = fields.Boolean(string='Is Managing Director', default=False)
    tin_no = fields.Char('TIN No')


class ResBankInherit(models.Model):
    _inherit = "res.bank"

    branch_name = fields.Char('Bank Branch Name')
