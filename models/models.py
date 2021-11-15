# -*- coding: utf-8 -*-


from odoo import api, fields, models, SUPERUSER_ID, _


class AccountPaymentTerm(models.Model):
    _inherit = 'account.payment.term'

    payment_code = fields.Char('Code', index=True)


class PaymentType(models.Model):
    _name = "purchase.payment.type"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Purchase Payment Type"
    _rec_name = "desc"

    desc = fields.Char(string="Name", required=True, )
    notes = fields.Text(string="Notes", required=False, )
    is_active = fields.Boolean(string="Active", )


class DeliveryTime(models.Model):
    _name = "purchase.delivery.time"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Purchase Delivery Time"
    _rec_name = "desc"

    desc = fields.Char(string="Name", required=True, )
    notes = fields.Text(string="Notes", required=False, )
    is_active = fields.Boolean(string="Active", )


class PurchaseGuaranteeType(models.Model):
    _name = 'purchase.guarantee.type'
    _description = 'Purchase Guarantee Type'
    _rec_name = "desc"

    desc = fields.Char(string="Name", required=True, )
    notes = fields.Text(string="Notes", required=False, )
    is_active = fields.Boolean(string="Active", )
