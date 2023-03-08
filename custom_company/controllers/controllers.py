# -*- coding: utf-8 -*-
from odoo import http

# class CustomCompany(http.Controller):
#     @http.route('/custom_company/custom_company/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/custom_company/custom_company/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('custom_company.listing', {
#             'root': '/custom_company/custom_company',
#             'objects': http.request.env['custom_company.custom_company'].search([]),
#         })

#     @http.route('/custom_company/custom_company/objects/<model("custom_company.custom_company"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('custom_company.object', {
#             'object': obj
#         })