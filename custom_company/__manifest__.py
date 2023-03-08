# -*- coding: utf-8 -*-
{
    'name': "Custom Company Module",

    'summary': """
        This module is designed to work for Good neighbours company organisation structure""",

    'description': """
        This module is designed to work for Good neighbours company organisation structure
    """,

    'author': "Xero 1 LTD",
    'website': "http://www.xero.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'company',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail', 'web', 'auth_signup', 'hr', 'hr_contract'],

    # always loaded
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}