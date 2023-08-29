# -*- coding: utf-8 -*-
import base64
from io import BytesIO

from odoo import models, fields, api, _
from odoo.http import request
from odoo.tools import datetime


class CustodianReportXLS(models.AbstractModel):
    _name = 'report.asset_management.asset_custodian_report_xls'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, lines):
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
        })
        cell_text_info_format.set_border()

        cell_text_employee_format = workbook.add_format({
            # 'bold': True,
            'font_name': 'Arial',
            'font_size': 8,
        })
        cell_text_employee_format.set_border()
        cell_text_info_body_format = workbook.add_format({
            'bold': True,
            'font_name': 'Arial',
            'font_size': 8,
            'align': 'center',
        })
        cell_text_info_body_format.set_border()
        cell_text_sub_title_format = workbook.add_format({
            # 'bold': True,
            'font_name': 'Arial',
            'font_size': 8,
        })
        cell_text_sub_title_format.set_border()
        cell_text_term_format = workbook.add_format({
            'valign': 'vcenter',
            'text_wrap': True,
            'font_name': 'Calibri',
            'font_size': 8,
        })
        cell_text_term_format.set_border()

        cell_text_signature_format = workbook.add_format({
            'align': 'right',
            'text_wrap': True,
            'font_name': 'Arial',
            'font_size': 11,
            'bold': True,
        })
        cell_text_signature_format.set_border()

        cell_text_body_format = workbook.add_format({
            'font_name': 'Arial',
            'font_size': 8,
        })
        cell_text_body_format.set_border()
        divider_format = workbook.add_format({'fg_color': '#9BBB59', })
        divider_format.set_border()
        worksheet.set_row(0, 85)
        worksheet.set_column('A:I', 13)
        company = self.env.user.company_id

        termsAndCondition = ("Important Notice\n\n"
                             "Greetings, " + lines.assigned_person.name + "\n"
                                                                          "You are being notified that you are the legal owner of the stated asset on this form. The items are in good condition without any physical damage or fault. Wherever you encounter difficulties, get assistance from the procurement team.\n"
                                                                          "Our organization is committed to ensuring that all organization assets and inventory are properly managed and accounted for at all times. As a member of GNTZ, it is your responsibility to adhere to the following guidelines: -\n"
                                                                          "1) Use of Organization Asset: All organization assets provided to you, including laptops, phones, and other equipment, are to be used solely for organization purposes. Personal use of these assets is strictly prohibited\n"
                                                                          "2) Care of organization assets: You are responsible for the proper care and maintenance of all organization assets issued to you. Please report any damage or malfunction to your supervisor immediately for repair or replacement\n"
                                                                          "3) Inventory control: All inventory items, including supplies and equipment, must be properly accounted for and stored in designated areas. Any discrepancies or issues with inventory must be reported to your supervisor immediately.\n"
                                                                          "4) Security: Ensure that all organization assets and inventory are stored in secure locations to prevent theft or loss. Do not share access codes or keys to storage areas with anyone who is not authorized to access them.\n"
                                                                          "Failure to comply with these guidelines may result in disciplinary action, up to and including termination of employment. We appreciate your cooperation in maintaining the integrity of our asset and inventory management system")
        signature = ("..................................................\n\n"
                     "Authorized signature and time"
                     )

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

        # Employee information's

        worksheet.write('A4:A4', 'Name of the Employee', cell_text_employee_format)
        worksheet.merge_range('B4:D4', lines.assigned_person.name, cell_text_info_body_format)
        worksheet.write('A5:A5', 'ID Number', cell_text_employee_format)
        worksheet.merge_range('B5:D5', '', cell_text_info_body_format)

        worksheet.write('A6:A6', 'Department', cell_text_employee_format)
        worksheet.merge_range('B6:D6', lines.assigned_person.department_id.name, cell_text_info_body_format)

        worksheet.write('E4:E4', 'Job Title', cell_text_employee_format)
        worksheet.merge_range('F4:I4', lines.assigned_person.job_title or '', cell_text_info_body_format)

        worksheet.write('E5:E5', 'Position', cell_text_employee_format)
        worksheet.merge_range('F5:I5', lines.assigned_person.job_id.name or '', cell_text_info_body_format)

        worksheet.write('E6:A6', 'Date', cell_text_employee_format)
        worksheet.merge_range('F6:I6', datetime.now().strftime('%m-%d-%Y'), cell_text_info_body_format)

        worksheet.merge_range('A7:I7', '', divider_format)

        # Extractor information
        worksheet.write('A8:A8', 'Extracted by', cell_text_info_format)
        worksheet.merge_range('B8:D8', user_name, cell_text_info_body_format)

        worksheet.write('A9:A9', 'Date', cell_text_info_format)
        worksheet.merge_range('B9:I9', datetime.now().strftime('%m-%d-%Y'), cell_text_info_body_format)

        worksheet.write('A10:A10', 'Email', cell_text_info_format)
        worksheet.merge_range('B10:D10', email, cell_text_info_body_format)

        worksheet.write('E8:E8', 'Designation', cell_text_info_format)
        worksheet.merge_range('F8:I8', job_position, cell_text_info_body_format)

        worksheet.write('E10:E10', 'Department', cell_text_info_format)
        worksheet.merge_range('F10:I10', department_name, cell_text_info_body_format)

        worksheet.merge_range('A11:I11', '', divider_format)

        worksheet.write('A12:A12', 'S/N', cell_text_sub_title_format)
        worksheet.write('B12:B12', 'Request', cell_text_sub_title_format)
        worksheet.write('C12:C12', 'Department', cell_text_sub_title_format)
        worksheet.write('D12:D12', 'Asset Name', cell_text_sub_title_format)
        worksheet.write('E12:E12', 'Asset ID', cell_text_sub_title_format)
        worksheet.write('F12:F12', 'Asset No', cell_text_sub_title_format)
        worksheet.write('G12:G12', 'Purchased Date', cell_text_sub_title_format)
        worksheet.write('H12:H12', 'Gross Value', cell_text_sub_title_format)
        worksheet.write('I12:I12', 'Condition', cell_text_sub_title_format)

        row = 12
        col = 0
        index = 1

        for requester in lines:
            for asset in requester.asset_ids:
                index = index
                requested = asset.category_id.name
                department = asset.department_id.name
                asset_name = asset.name
                asset_id = asset.asset_id_no
                asset_no = asset.code
                purchase_date = datetime.strftime(asset.date, '%d-%m-%Y')
                value = asset.value

                worksheet.write(row, col, index or '', cell_text_body_format)
                worksheet.write(row, col + 1, requested or '', cell_text_body_format)
                worksheet.write(row, col + 2, department or '', cell_text_body_format)
                worksheet.write(row, col + 3, asset_name or '', cell_text_body_format)
                worksheet.write(row, col + 4, asset_id or '', cell_text_body_format)
                worksheet.write(row, col + 5, asset_no or '', cell_text_body_format)
                worksheet.write(row, col + 6, purchase_date or '', cell_text_body_format)
                worksheet.write(row, col + 7, value or '', cell_text_body_format)
                worksheet.write(row, col + 8, '', cell_text_body_format)

                row = row + 1
                index = index + 1
        worksheet.set_row(row, 205)
        worksheet.set_row(row + 1, 60)
        worksheet.merge_range(row, col, row, col + 8, termsAndCondition, cell_text_term_format)
        worksheet.merge_range(row + 1, col, row + 1, col + 8, signature, cell_text_signature_format)

        # Set up page break preview
        worksheet.set_v_pagebreaks([row])  # Add a vertical page break after the specified row

        # Set paper size to A4
        worksheet.set_paper(9)  # 9 corresponds to A4 size
        # Close the workbook
        workbook.close()
