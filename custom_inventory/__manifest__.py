# -*- coding: utf-8 -*-
{
    'name': "Inventory Management",

    'summary': """
        Inventory Management,Stock In and Out""",

    'description': """
        Inventory Management,Stock In and Out
    """,

    'author': "Xero 1 LTD",
    'website': "http://www.xero.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'purchase',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','mail','account','product','uom', 'stock'],

    # always loaded
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/email_template.xml',
        'views/views.xml',
        'views/stock_adjustment.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}