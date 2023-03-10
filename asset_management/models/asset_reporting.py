from odoo import models, fields, api, _


class AssetReportingDamage(models.Model):
    _name = 'asset.reporting.damage'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    electronic_asset = fields.Selection(string="is the damage for electronic asset?",
                                        selection=[('yes', 'Yes'),
                                                   ('no', 'No'),
                                                   ],
                                        default='no',
                                        required=True, )

    SELECTION = [
        ('draft', 'Draft'),
        ('submit', 'Submitted'),
        ('line_manager', 'Line Manager'),
        ('it_officer', 'IT Officer'),
        ('procurement', 'Procurement'),
        ('adm_cd', 'AD Manager/Country Director')
    ]

    IT_SELECTION = [
        ("draft_it", "Draft"),
        ("submit_it", "Submitted"),
        ("line_manager_it", "Line Manager"),
        ("it_officer_it", "IT Officer"),
        ("procurement_it", "Procurement"),
        ("adm_cd_it", "AD Manager/Country Director"),
    ]

    @api.multi
    def button_staff_submit_damage(self):
        for asset in self.asset_reporting_damage_line_ids:
            asset.write({'state': 'submit'})
        self.write({'state': 'submit'})
        return True

    @api.multi
    def button_staff_submit_damage_it(self):
        for asset in self.asset_reporting_damage_line_ids:
            asset.write({'IT_state': 'submit_it'})
        self.write({'IT_state': 'submit_it'})
        return True

    @api.multi
    def button_line_manager_review(self):
        for asset in self.asset_reporting_damage_line_ids:
            asset.write({'state': 'line_manager'})
        self.write({'state': 'line_manager'})
        return True

    @api.multi
    def button_line_manager_review_it(self):
        for asset in self.asset_reporting_damage_line_ids:
            asset.write({'IT_state': 'line_manager_it'})
        self.write({'IT_state': 'line_manager_it'})
        return True

    @api.multi
    @api.depends('recommendation')
    def button_procurement_review(self):
        if self.recommendation == "repair":
            for asset in self.asset_reporting_damage_line_ids:
                asset.write({'state': 'procurement'})
                for reported_asset in asset.name:
                    for asset_name in reported_asset.asset_ids:
                        asset_name.write({'state': 'repair'})
            self.write({'state': 'procurement'})
            return True
        else:
            for asset in self.asset_reporting_damage_line_ids:
                asset.write({'state': 'procurement'})
                for reported_asset in asset.name:
                    for asset_name in reported_asset.asset_ids:
                        asset_name.write({'state': 'close'})
            self.write({'state': 'procurement'})
            return True

    @api.multi
    def button_procurement_review_it(self):
        for asset in self.asset_reporting_damage_line_ids:
            asset.write({'IT_state': 'procurement_it'})
        self.write({'IT_state': 'procurement_it'})
        return True

    @api.multi
    def button_ict_officer_recommend(self):
        for asset in self.asset_reporting_damage_line_ids:
            asset.write({'state': 'it_officer'})
        self.write({'state': 'it_officer'})
        return True

    @api.multi
    def button_ict_officer_recommend_it(self):
        for asset in self.asset_reporting_damage_line_ids:
            asset.write({'IT_state': 'it_officer_it'})
        self.write({'IT_state': 'it_officer_it'})
        return True

    @api.multi
    def button_am_manager_review(self):
        for asset in self.asset_reporting_damage_line_ids:
            asset.write({'state': 'adm_cd'})
        self.write({'state': 'adm_cd'})
        return True

    @api.multi
    def button_am_manager_review_it(self):
        for asset in self.asset_reporting_damage_line_ids:
            asset.write({'IT_state': 'adm_cd_it'})
        self.write({'IT_state': 'adm_cd_it'})
        return True

    def _default_employee(self):
        return self.env.context.get('default_employee_id') or self.env['hr.employee'].search(
            [('user_id', '=', self.env.uid)], limit=1).id

    name = fields.Many2one(comodel_name='hr.employee', string='Employee Name',
                           required=True, default=_default_employee, readonly=True)
    state = fields.Selection(SELECTION, index=True, track_visibility='onchange',
                             default='draft', required=True)
    IT_state = fields.Selection(IT_SELECTION, index=True, track_visibility='onchange',
                                default='draft_it', required=True)
    # electronic_asset = fields.Boolean(string='is the damage for electronic asset?', default=False)
    recommendation = fields.Selection(string="Line Manager recommendation",
                                      selection=[('repair', 'Repair'),
                                                 ('replace', 'Replace'),
                                                 ],
                                      default='repair',
                                      required=False, )
    line_manager_comment = fields.Text(string='Line Manager Recommendation comment')
    ict_officer_comment = fields.Text(string='ICT Officer Recommendation comment')
    procurement_comment = fields.Text(string='Procurement comment')
    employee_no = fields.Char(string='Employee Number', related='name.work_phone')
    position = fields.Char(string='Position/Title', related='name.job_id.name')
    department = fields.Char(string='Department', related='name.department_id.name')
    phone = fields.Char(string='Phone', related='name.work_phone')
    email = fields.Char(string='Email', related='name.work_email')

    # Incident information
    incident_date = fields.Date(string="Incident Date")
    report_date = fields.Date(string="Report Date")
    incident_location = fields.Char(string="Incident Location")
    asset_reporting_damage_line_ids = fields.One2many(comodel_name="asset.reporting.damage.line",
                                                      inverse_name="asset_reporting_damage_id",
                                                      string="Asset Reporting damage line",
                                                      required=False, )
    damage_asset_name = fields.Char(string="Damage Asset", related="asset_reporting_damage_line_ids.name.asset_name")
    # damage_asset_name = fields.Char(string="Damage Asset", related="asset_reporting_damage_line_ids.location")


class AssetReportingDamageLine(models.Model):
    _name = 'asset.reporting.damage.line'

    SELECTION = [
        ("draft", "Draft"),
        ("it_officer", "IT officer"),
        ("submit", "Submitted"),
        ("line_manager", "Line Manager"),
        ("procurement", "Procurement"),
        ("adm_cd", "AD Manager/Country Director"),
    ]

    IT_SELECTION = [
        ("draft_it", "Draft"),
        ("submit_it", "Submitted"),
        ("line_manager_it", "Line Manager"),
        ("it_officer_it", "IT Officer"),
        ("procurement_it", "Procurement"),
        ("adm_cd_it", "AD Manager/Country Director"),
    ]
    state = fields.Selection(SELECTION, index=True, track_visibility='onchange',
                             default='draft')
    IT_state = fields.Selection(IT_SELECTION, index=True, track_visibility='onchange',
                                default='draft_it')
    name = fields.Many2one(comodel_name="account.asset.assign", string="Asset")
    identification_number = fields.Char(string="Code", related="name.asset_number")
    location = fields.Char(string="Location")
    damage_description = fields.Text(string="Description")
    cost = fields.Char(string="Estimated Cost ")
    person_responsible = fields.Many2one(comodel_name="res.users", string="Person responsible")
    asset_reporting_damage_id = fields.Many2one(comodel_name="asset.reporting.damage", string="Reporting damage ID",
                                                required=False)


class AssetReportingLost(models.Model):
    _name = 'asset.reporting.lost'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    SELECTION = [
        ("draft", "Draft"),
        ("line_manager", "Line Manager"),
        ("procurement", "Procurement"),
        ("adm_cd", "AD Manager/Country Director"),
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
        for asset in self.equipment_name:
            asset.write({'state': 'close'})
        self.write({'state': 'adm_cd'})
        return True

    name = fields.Many2one(comodel_name='hr.employee', string='Employee Name',
                           required=True)
    state = fields.Selection(SELECTION, index=True, track_visibility='onchange',
                             default='draft')
    employee_no = fields.Char(string='Employee Number', related='name.work_phone')
    position = fields.Char(string='Position/Title', related='name.job_id.name')
    department = fields.Char(string='Department', related='name.department_id.name')
    phone = fields.Char(string='Phone', related='name.work_phone')
    email = fields.Char(string='Email', related='name.work_email')

    # Incident information
    incident_date = fields.Date(string="Incident Date")
    report_date = fields.Date(string="Report Date")
    incident_location = fields.Char(string="Incident Location")

    # Equipment information
    equipment_name = fields.Many2one(comodel_name="account.asset.asset", string="Asset")
    identification_number = fields.Char(string="Code", related="equipment_name.code")
    location = fields.Char(string="Location")
    damage_description = fields.Text(string="Description")
    cost = fields.Float(string="Estimated Cost ")
    person_responsible = fields.Many2one(comodel_name="res.users", string="Person responsible")
    police_file = fields.Binary(string="Police File", attachment=True, store=True, )
    police_file_name = fields.Char('Police File Name')
    office_incharge = fields.Char('Officer In Charge:')
    station = fields.Char('Station ')
    police_phone = fields.Char('Phone')
    police_email = fields.Char('Email')
    police_report = fields.Selection(string="Was the Equipment Lost / stolen reported to the Police?",
                                     selection=[('yes', 'Yes'),
                                                ('no', 'No'),
                                                ],
                                     default='no',
                                     required=False, )
