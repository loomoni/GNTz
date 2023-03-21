# -*- coding: utf-8 -*-
{
    'name': "Asset Management",

    'summary': """Asset Management ie Disposal, Revaluation and Fixed Asset Report""",

    'description': """
        Asset Management ie Disposal, Revaluation and Fixed Asset Report
    """,

    'author': "Xero1 Africa",
    'website': "http://www.xero1.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'assets',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'om_account_asset'],

    # always loaded
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'reports/report.xml',
        'reports/report_template.xml',
        'views/views.xml',
        'views/templates.xml',
        'views/asset_assign.xml',
        'views/asset_disposal.xml',
        'views/asset_reporting.xml',
        'views/asset_transfer.xml',
        'views/assets_checkout.xml',
        'views/assets_custodian.xml',
        'views/asset_reevaluation.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
