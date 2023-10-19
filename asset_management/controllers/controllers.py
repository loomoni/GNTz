import qrcode
from io import BytesIO
from odoo import http, _
from odoo.http import request


class AssetQRCodeController(http.Controller):

    @http.route('/report/asset_management_qr_code_template/generate_qr_code', type='http', auth="public")
    def generate_qr_code(self, asset_id):
        asset = request.env['account.asset.asset'].browse(int(asset_id))
        data = f"{asset.name} | {asset.code} | {asset.department_id.name if asset.department_id else ''} | {asset.category_id.name if asset.category_id else ''}"
        print(data)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        img_buffer = BytesIO()
        img.save(img_buffer, format="PNG")

        response = http.Response(
            img_buffer.getvalue(),
            content_type='image/png',
        )
        response.render()

        return response


# -*- coding: utf-8 -*-
# from odoo import http

# class AssetManagement(http.Controller):
#     @http.route('/asset_management/asset_management/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/asset_management/asset_management/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('asset_management.listing', {
#             'root': '/asset_management/asset_management',
#             'objects': http.request.env['asset_management.asset_management'].search([]),
#         })

#     @http.route('/asset_management/asset_management/objects/<model("asset_management.asset_management"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('asset_management.object', {
#             'object': obj
#         })
