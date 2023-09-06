# -*- coding: utf-8 -*-
import json

from odoo import models, fields, api, _
import logging
import requests
from odoo import api, models
import traceback
from datetime import datetime, timedelta
from odoo.modules import get_module_resource
from odoo.exceptions import ValidationError, UserError
from dateutil import relativedelta
from odoo.tools import config
_logger = logging.getLogger(__name__)


class BillSubmission(models.Model):
    _name = 'bill.submission'
    _description = 'Bill Submission'
    name = fields.Char(string='Bill Submission', required=True)

class ResPartnerInherited(models.Model):
    _inherit = 'res.partner'

    config = open(get_module_resource('quotations_orders', 'static/gst_code_mapping.json'), 'r').read()
    gst_code_mapping = json.loads(config)

    def _get_state_from_gst(self, gstn):
        gst_state_code = gstn[0:2]
        state_code = self.gst_code_mapping[gst_state_code]
        country_id = self.env['res.country'].search([('code', '=', 'IN')], limit=1).id
        state = self.env['res.country.state'].search([('code', '=', state_code), ('country_id', '=', country_id)])
        return state.name if state else ""

class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    @api.model
    def _get_default_country(self):
        country = self.env['res.country'].search([('code', '=', 'IN')], limit=1)
        return country

    jobsite_id = fields.Many2one('jobsite', string='Site Name')
    tentative_quo = fields.Boolean('Tentative Quotation', default=False)
    order_type = fields.Selection([
        ('Rental', 'Rental'),
        ('Sale', 'Sale')],
        string="Order Type",
        default='Rental')

    partner_id = fields.Many2one(
        'res.partner', string='Customer', readonly=True,
        states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
        required=True, change_default=True, index=True, tracking=1,
        domain="[('is_company', '=', True),('is_customer_branch', '=', False)]",)

    validity_date = fields.Date(invisible=True)
    job_order = fields.Char(string="Job Order")

    place_of_supply = fields.Many2one("res.country.state", string='Place of Supply', ondelete='restrict')
    order_duration = fields.Char(string="Order Duration", compute="_compute_duration", store=False)
    def _compute_duration(self):
        if self.delivery_date and self.pickup_date:
            delta = relativedelta.relativedelta(self.pickup_date + timedelta(days=1), self.delivery_date)
            months = 0
            if delta.months:
                months = delta.months
            if delta.year:
                months = months + delta.year * 12

            self.order_duration = "{} Months and {} Days".format(months, delta.days)
        else:
            self.order_duration = False

    place_of_supply = fields.Many2one("res.country.state", string='Place of Supply', ondelete='restrict')
    remark = fields.Char(string="Remark")

    customer_branch = fields.Many2one(comodel_name='res.partner', string='Branch Name', domain="[('is_company', "
                                                                                                 "'=', True), "
                                                                                                 "('is_customer_branch', '=', True), ('parent_id', '=', partner_id)]")

    billing_addresses = fields.Many2one(comodel_name='res.partner', string='Billing Addresses',
                                        domain="[('is_company','=', False),('is_customer_branch', '=', False), ('parent_id', '=', customer_branch), ('type', '=', 'invoice')]")

    po_number = fields.Char(string="PO Number")
    po_amount = fields.Char(string="PO Amount")
    po_date = fields.Date(string='PO Date')

    po_details = fields.One2many('sale.order.po.details', 'sale_order_id', string='Child Companies')
    bank = fields.Char(string='Bank')
    cheque_number = fields.Char(string='Cheque Number', default=None)
    cheque_date = fields.Date(string='Cheque Date', default=None)
    cheque_amount = fields.Monetary(string='Cheque Amount')

    beta_quot_id = fields.Integer()

    # Billing Address
    billing_street = fields.Char(string="Billing Address")
    billing_street2 = fields.Char()
    billing_city = fields.Char()
    billing_country_id = fields.Many2one('res.country', string='Billing Country', ondelete='restrict',  default=_get_default_country)
    billing_state_id = fields.Many2one("res.country.state", string='Billing State', ondelete='restrict', domain="[('country_id', '=', billing_country_id)]")
    billing_zip = fields.Char(string='Billing Pincode', change_default=True)

    # Delivery Address
    delivery_street = fields.Char(string="Delivery Address")
    delivery_street2 = fields.Char()
    delivery_city = fields.Char()
    delivery_country_id = fields.Many2one('res.country', string='Delivery Country', ondelete='restrict', default=_get_default_country)
    delivery_state_id = fields.Many2one("res.country.state", string='Delivery State', ondelete='restrict',  domain="[('country_id', '=', delivery_country_id)]")

    bill_submission_office_branch = fields.Many2one(comodel_name='res.partner', string='Customer Bill Submission Branch', domain="[('is_company', "
                                                                                                                               "'=', True), "
                                                                                                                               "('is_customer_branch', '=', True), ('parent_id', '=', partner_id)]")

    bill_submission_email = fields.Char(string='Bill Submission Email')

    delivery_zip = fields.Char(string='Delivery Pincode', change_default=True)

    email_to = fields.Char(string='Email To')

    pickup_date = fields.Date('Pickup Date')




    @api.onchange('tentative_quo')
    def _onchage_tentative_quotation(self):
        if self.tentative_quo:
            return  {'domain': {'partner_id': ['|', '&', ('is_company', '=', True), ('is_customer_branch', '=', False), ('is_company', '=', False)]}}
        else:
            if self.partner_id and not (self.partner_id.is_company and not self.partner_id.is_customer_branch):
                self.partner_id = False
            return  {'domain': {'partner_id': [('is_company', '=', True),('is_customer_branch', '=', False)]}}

    @api.onchange('purchaser_name')
    def _onchange_purchaser_name(self):
        self.email_to = self.purchaser_name.email if self.purchaser_name is not False else ""

    @api.model
    def _get_default_godowns(self):
        godown = self.env['jobsite.godown'].search([('id', 'in', self.jobsite_id.godown_id)]).name
        return godown

    godown = fields.Many2one("jobsite.godown", string='Parent Godown', ondelete='restrict')
    bill_godown = fields.Many2one("jobsite.godown", string='Billing Godown', ondelete='restrict')
    site_bill_submission_godown = fields.Many2one("jobsite.godown", string='Youngman Bill Submission Site Godown', ondelete='restrict')
    office_bill_submission_godown = fields.Many2one("jobsite.godown", string='Youngman Bill Submission Office Godown', ondelete='restrict')

    delivery_date = fields.Date('Delivery Date')
    security_amount = fields.Monetary(string="Security Amount", currency_field='currency_id')
    freight_amount = fields.Monetary(string="Freight Amount", currency_field='currency_id')
    freight_paid_by = fields.Selection([
        ('freight_type1', 'It has been agreed 1st Dispatch and final Pickup will be done by Youngman'),
        ('freight_type2', 'It has been agreed 1st Dispatch will be done by Youngman and final Pickup will be done by Customer on his cost'),
        ('freight_type3', 'It has been agreed 1st Dispatch will be done by Customer on his cost and final Pickup would be done by Youngman'),
        ('freight_type4', 'It has been agreed 1st Dispatch will be done by Customer on his cost and final Pickup is already paid by Customer'),
        ('freight_type5', 'It has been agreed 1st Dispatch and final Pickup will be done by Customer on his cost')],
        string="Freight Terms ",
        default='freight_type1')

    price_type = fields.Selection([
        ('daily', 'Daily'),
        ('monthly', 'Monthly')],
        string="Price Type",
        default='monthly')

    purchaser_name = fields.Many2one("res.partner", string='Purchaser Name', domain="[('parent_id', '=', partner_id),('category_id','ilike','purchaser'),('is_company', '=', False)]")
    site_contact_name = fields.Many2one("res.partner", string='Site Contact Name', domain="[('parent_id', '=', partner_id),('is_company','=', False),('category_id','ilike','site contact')]")
    bill_site_contact = fields.Many2one(comodel_name='res.partner', string='Bill Submission Site Contact', domain="[('is_company', '=', False), ('parent_id', '=', partner_id), ('category_id','ilike','site contact')]")
    bill_office_contact = fields.Many2one(comodel_name='res.partner', string='Customer Bill Submission Office Contact', domain="[('is_company', '=', False), ('parent_id', '=', partner_id),('category_id','ilike','office contact')]")

    below_min_price = fields.Boolean('Below Min Price', default=False)

    otp = fields.Integer(string='OTP')
    otp_verified = fields.Boolean(string='OTP', default=False)  # TODO compute field should be equal to

    is_rental_advance = fields.Boolean(related='customer_branch.rental_advance', store=False)
    is_rental_order = fields.Boolean(related='customer_branch.rental_order', store=False)
    is_security_cheque = fields.Boolean(related='customer_branch.security_cheque', store=False)
    is_rental_advance = fields.Boolean(related='partner_id.rental_advance', store=False)
    is_rental_order = fields.Boolean(related='partner_id.rental_order', store=False)
    is_security_cheque = fields.Boolean(related='partner_id.security_cheque', store=False)
    bill_submission_process = fields.Char(related='partner_id.bill_submission_process.name', store=False)
    bill_submission_process_code = fields.Char(related='partner_id.bill_submission_process.code', store=False)

    rental_advance = fields.Binary(string="Rental Advance")
    rental_order = fields.Binary(string="Rental Order")
    security_cheque = fields.Binary(string="Security Cheque")
    payment_reciept = fields.Binary(string="Payment Reciept")

    def open_sale_order_po_details(self):
        if not self.id:
            raise UserError(_('You must save the Sale Order before adding a PO Detail.'))
        return {
            'name': _('Sale Order PO Details'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.po.details',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'context': {'default_sale_order_id': self.id},
        }

    @api.model
    def _amount_all(self):
        super(SaleOrderInherit, self)._amount_all()
        for order in self:


            amount_untaxed = order.amount_untaxed * ((self.pickup_date - self.delivery_date).days + 1) if self.price_type == 'daily' else order.amount_untaxed

            amount_tax = ((amount_untaxed * 18) / 100) + ((order.freight_amount * 18) / 100)

            if self.price_type == 'daily':
                days_due = (self.pickup_date - self.delivery_date).days + 1
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,

                'amount_total': amount_untaxed + amount_tax + order.freight_amount,

            })
    @api.depends('order_line.tax_id', 'order_line.price_unit', 'amount_total', 'freight_amount')
    def _compute_tax_totals_json(self):
        def compute_taxes(order_line):
            price = order_line.price_unit * (1 - (order_line.discount or 0.0) / 100.0)
            order = order_line.order_id
            return order_line.tax_id._origin.compute_all(price, order.currency_id, order_line.product_uom_qty,
                                                         product=order_line.product_id,
                                                         partner=order.partner_shipping_id)

        account_move = self.env['account.move']
        for order in self:
            tax_lines_data = account_move._prepare_tax_lines_data_for_totals_from_object(order.order_line,
                                                                                         compute_taxes)
            tax_id = self.env['account.tax'].sudo().search([('type_tax_use', '=', 'sale'), ('amount','=',18)])

            if order.freight_amount:
                tax_lines_data.append({'line_key': "tax_line_freight_1", "tax_amount": order.freight_amount * tax_id.amount/100,"tax": tax_id})
                tax_lines_data.append({'line_key': "base_line_freight", "base_amount": order.freight_amount, "tax": tax_id})

            amount_untaxed = sum(item.get('base_amount', 0) for item in tax_lines_data)
            tax_amount = sum(item.get('tax_amount', 0) for item in tax_lines_data)

            days_due = 1  # Default value for monthly price type
            if order.price_type == 'daily':
                days_due = (order.pickup_date - order.delivery_date).days + 1
                amount_untaxed = (amount_untaxed - order.freight_amount) * days_due
                amount_total = amount_untaxed + order.freight_amount + (amount_untaxed * 18)/100 + (order.freight_amount * 18)/100
            else:
                amount_total = tax_amount + amount_untaxed

            tax_totals = account_move._get_tax_totals(order.partner_id, tax_lines_data, amount_total,
                                                      amount_untaxed, order.currency_id)
            tax_totals['freight'] = order.freight_amount
            tax_totals['formatted_freight'] = "Rs. " + str(order.freight_amount)
            tax_totals['freight_tax'] = order.freight_amount * tax_id.amount/100
            tax_totals['formatted_freight_tax'] = "Rs. " + str(order.freight_amount * tax_id.amount/100)
            order.tax_totals_json = json.dumps(tax_totals)


    @api.onchange('purchaser_name')
    def get_purchaser_phone(self):
        if self.purchaser_name:
            if not self.purchaser_name.email:
                raise ValidationError(_("Purchaser does not have Email"))

    @api.onchange('jobsite_id')
    def get_delivery_address(self):
        if self.jobsite_id:
            self.delivery_street = self.jobsite_id.street
            self.delivery_street2 = self.jobsite_id.street2
            self.delivery_city = self.jobsite_id.city
            self.delivery_state_id = self.jobsite_id.state_id
            self.delivery_country_id = self.jobsite_id.country_id
            self.delivery_zip = self.jobsite_id.zip
            self.godown = self.jobsite_id.godown_id

    @api.onchange('order_line')
    def price_change(self):
        # if self.below_min_price == True and self.otp_verified==True:
        #     return

        pricelist_id = self.pricelist_id.id
        for order_line in self.order_line:
            product_id =order_line.product_id.id
            product_data = self.env['product.pricelist.item'].sudo().search(
                    [('pricelist_id', '=', pricelist_id), ('product_id', '=', product_id)], limit=1)

            unit_price = product_data.fixed_price if product_data else self.env['product.product'].search(
                    [('id', '=', product_id)], limit=1).list_price

            current_price = order_line.price_unit
            if current_price< unit_price:
                if order_line.is_item_verified==True:
                    pass
                else:
                    self.below_min_price = True
                    order_line.price_unit = unit_price
                    # return self.get_notifcation_message("Wrong", "Wrong OTP", "danger")
                    return {
                        'warning': {
                            'title': 'Warning',
                            'message': 'You are attempting to enter a price for the product that is less than its unit price.Please Verifiy using otp.',
                        },
                    }



    def action_confirm(self):
        # https://www.odoo.com/forum/help-1/how-to-insert-value-to-a-one2many-field-in-table-with-create-method-28714
        if self.po_amount and self.po_number and self.po_date:
            self.po_details = [
                [0, 0, {
                    'po_amount': self.po_amount,
                    'po_number': self.po_number,
                    'po_date': self.po_date,
                    'pickup_date': self.pickup_date
                }]
            ]

        super(SaleOrderInherit, self).action_confirm()

    @api.model_create_multi
    def create(self, vals):
        for val in vals:
           if not val.get('opportunity_id'):
               raise UserError("There is no opportunity linked with this quotation")




        return super(SaleOrderInherit, self).create(vals)
    def _get_allowed_fields(self):
        return ['order_line', 'pickup_date','po_number','po_amount','rental_order','freight_amount', 'show_update_pricelist', 'name', 'po_date']

    def write(self, vals):
        # When a mail is being sent, write method gets called with an empty object. So add a check for Id
        if self.id and (not self.opportunity_id or not self.opportunity_id.id):
            raise UserError("There is no opportunity linked with this quotation")
        if self.job_order != False and ('job_order' not in vals) and ('pickup_date' in vals) and self.pickup_date != vals['pickup_date']:
            allowed_fields = self._get_allowed_fields()
            for field in vals:
                if field not in allowed_fields:
                    raise UserError(
                        "You can change only two things Pickup date and Orderlines After Job_order Confirmed")
        super(SaleOrderInherit, self).write(vals)


    @api.onchange('partner_id')
    def clear_customer_branch(self):
        if self.partner_id:
            self.customer_branch = False
            self.billing_street = False
            self.billing_street2 = False
            self.billing_city = False
            self.billing_state_id = False
            self.billing_zip = False
            self.billing_country_id = False

        if ((self.partner_id) and (self.tentative_quo is False)) and (
                (self.partner_id.is_company is False) or (self.partner_id.is_customer_branch is True)):
            raise ValidationError(_("Please select a Company"))

    @api.onchange('billing_addresses')
    def get_billing_address(self):
        if self.billing_addresses:
            self.billing_street = self.billing_addresses.street
            self.billing_street2 = self.billing_addresses.street2
            self.billing_city = self.billing_addresses.city
            self.billing_state_id = self.billing_addresses.state_id
            self.billing_zip = self.billing_addresses.zip
            self.billing_country_id = self.billing_addresses.country_id

    def verify_otp(self):
        otp = self._generate_otp()
        if self.otp == int(otp):
            for order_line in self.order_line:
                if order_line.is_item_verified==True:
                    pass
                else:
                    order_line.is_item_verified=True
            self.otp_verified = True

            return self.get_notifcation_message("Success", "OTP Verified", "success")
        else:
            return self.get_notifcation_message("Wrong", "Wrong OTP", "danger")

    def get_notifcation_message(self, name, msg, type):
        notification = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': (name),
                'message': msg,
                'type': type,  # types: success,warning,danger,info
                'sticky': False,  # True/False will display for few seconds if false
            },
        }
        return notification

    def request_otp(self):
        if self.team_id.name=='INSIDE SALES':
            number=self.env['ir.config_parameter'].sudo().get_param('ym_sms.sales_head_contact_inside_sales')
        else:
            number = self.env['ir.config_parameter'].sudo().get_param('ym_sms.sales_head_contact_pam')
        message="OTP:- {} Youngman India Pvt. Ltd.".format(self._generate_otp())
        self.env['ym.sms'].send_sms_to_number(number, message)


    def _generate_otp(self):
        now = datetime.now()

        code = now.year * now.month * now.day * now.hour * now.minute
        code = str(code * 1000000)

        return code[:6]


    def _get_nearest_godown(self, pincode):
        endpoint = self.env['ir.config_parameter'].sudo().get_param('ym_configs.nearest_godown_endpoint') + str(pincode)
        try:
            response = requests.get(endpoint, verify=False)
            return response.json()
        except requests.HTTPError:
            error_msg = _("Could not fetch nearest Godown. Remote server returned status ???")
            raise self.env['res.config.settings'].get_config_warning(error_msg)
        except Exception as e:
            error_msg = _("Some error occurred while fetching nearest Godown")
            raise self.env['res.config.settings'].get_config_warning(error_msg)
        finally:
            traceback.format_exc()



class ProductTemplateInherit(models.Model):
    _name = 'product.template'
    _inherit = 'product.template'

    detailed_type = fields.Selection(default='service', readonly=True)
    invoice_policy = fields.Selection(default='delivery', readonly=True)

    status = fields.Selection([
        ('0', 'ACTIVE'),
        ('1', 'DEACTIVE'),
        ('2', 'DISABLE'),
    ], string='Status')

    bundle = fields.Boolean(default=False, string="Bundle")
    consumable = fields.Boolean(default=False, string="Consumable")
    serialized = fields.Boolean(default=False, string="Serialized")
    list_price = fields.Float('Rental Price', digits=(12, 2), required=True, default=0.0)
    meters = fields.Float('Meters', default=0.0)
    length = fields.Float('Length (inch)', default=0.0)
    breadth = fields.Float('Breadth (inch)', default=0.0)
    height = fields.Float('Height (inch)', default=0.0)
    actual_weight = fields.Float('Actual Weight (kg)', default=0.0)
    vol_weight = fields.Float('Volume Weight', default=0.0)
    cft = fields.Float('CFT (cu ft)', default=0.0)
    missing_estimate_value = fields.Float('Missing Estimate Value', digits=(12, 2), default=0.0)
    material = fields.Text(string="Material")
    item_type = fields.Char(string="Item Type")
    purchase_code = fields.Char(string="Purchase Code")
    supplier = fields.Char(string="Supplier")
    standard_price = fields.Float(
        'Estimate Value', company_dependent=True, digits=(12, 2),
        groups="base.group_user", )
    list_price = fields.Float('Rental Price')
    default_code = fields.Char(string="Product Code")


class SaleOrderLineInherit(models.Model):
    _inherit = 'sale.order.line'
    _description = 'sale.order.line'

    item_code = fields.Char(string="Item Code")
    beta_quot_item_id = fields.Integer()
    is_item_verified=fields.Boolean()


