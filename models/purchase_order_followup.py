# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression


class PurchaseOrderFollowup(models.Model):
    _name = 'purchase.order.followup'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']
    _description = 'Purchase Order Followup'
    _order = 'id desc'

    name = fields.Char(string='Followup Reference', required=True, copy=False, readonly=True,
                       states={'draft': [('readonly', False)]}, index=True, default=lambda self: _('New'))
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approve', 'Approved'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True, tracking=3, default='draft')
    date_followup = fields.Date(string='Followup Date', readonly=True, copy=False,
                                states={'draft': [('readonly', False)]}, default=fields.Date.context_today)

    user_id = fields.Many2one(
        'res.users', string='Purchase Person', index=True, tracking=2, default=lambda self: self.env.user)
    partner_id = fields.Many2one('res.partner', string='Vendor', readonly=True, related='purchase_id.partner_id',
                                 store=True)
    purchase_id = fields.Many2one("purchase.order", string="Purchase Order", domain="[('state', '=', 'purchase')]")
    date_order = fields.Datetime(string='Order Date', readonly=True, copy=False, related='purchase_id.date_order',
                                 store=True, states={'draft': [('readonly', False)]}, default=fields.Date.context_today)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id.id)
    note = fields.Text('Notes')

    amount_total = fields.Monetary(string='Total', store=True, readonly=True, related='purchase_id.amount_total', )

    payment_term_id = fields.Many2one('account.payment.term', 'Payment Terms', related='purchase_id.payment_term_id',
                                      domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    payment_code = fields.Char('Code', index=True, related='payment_term_id.payment_code')
    currency_id = fields.Many2one('res.currency', 'Currency', store=True,
                                  related='purchase_id.currency_id')
    currency_rate = fields.Float("Currency Rate", related='purchase_id.currency_rate', store=True, readonly=True,
                                 help='Ratio between the purchase order currency and the company currency')

    @api.depends('date_order', 'currency_id', 'company_id', 'company_id.currency_id')
    def _compute_currency_rate(self):
        for order in self:
            order.currency_rate = self.env['res.currency']._get_conversion_rate(order.company_id.currency_id,
                                                                                order.currency_id, order.company_id,
                                                                                order.date_order)

    # in advance
    adv_trans_date = fields.Date(string='Date Of Transfer', states={'draft': [('readonly', False)]},
                                 default=fields.Date.context_today)
    adv_amount = fields.Monetary(string='Advance Amount', store=True, default=0)
    bank_id = fields.Many2one(comodel_name="res.bank", string="Advance Bank", required=False, )

    # LC
    lc_no = fields.Char(string="L.C Number", required=False, )
    lc_date = fields.Date(string="Date", required=False, )
    lc_total = fields.Monetary(string='L.C Amount', store=True, )
    lc_expire_date = fields.Date(string="Expire Date", required=False, )
    lc_latest_shipment_date = fields.Date(string="Latest Shipment Date", required=False, )
    lc_issue_bank = fields.Many2one(comodel_name="res.bank", string=" Issue Bank", required=False, )
    lc_corress_bank = fields.Many2one(comodel_name="res.bank", string=" Correspondent Bank", required=False, )
    lc_state = fields.Selection(string="L.C Status", required=False,
                                selection=[('confirmed', 'Confirmed'), ('unconfirmed', 'Un Confirmed'), ], )
    hs_code = fields.Char(string="HS.Code", required=False, )
    lc_extend_validity = fields.Date(string="Extention OF LC Validity", required=False, )
    lc_latest_extend_validity = fields.Date(string="Extention OF Latest Date OF Shipment", required=False, )

    # shipping
    shipment_date = fields.Date(string="Shipment Date", required=False, )
    shipment_amount = fields.Monetary(string='Shipment Amount', store=True, )
    date_arrival = fields.Date(string="Vessel/Airplane Arrival Date", required=False, )
    date_bank_doc_arrival = fields.Date(string="Documents Arrival-Bank Date", required=False, )
    date_bank_doc_receive = fields.Date(string="Receiving Bank.Docs DATE", required=False, )
    date_bank_doc_deliver_alex = fields.Date(string="Deliver Docs.Alex.Sector Date", required=False, )
    date_receipt_tranzit = fields.Date(string="Receipt Goods-Tranzit Date", required=False, )
    date_receipt_fact = fields.Date(string="Receipt Goods-Factories Date", required=False, )
    shipment_status = fields.Selection(string="Shipment Status",
                                       selection=[('identical', 'Identical'), ('notidentical', 'Non-Identical'),
                                                  ('missing', 'Missing'), ], required=False, )
    date_delivery_note = fields.Date(string="Delivery Note Dated", required=False, )

    # lg
    lg_no = fields.Char(string="L.G Number", required=False, )
    lg_bank_id = fields.Many2one(comodel_name="res.bank", string="L.G Bank", required=False, )
    lg_type = fields.Many2one(comodel_name="purchase.guarantee.type", string="L.G Type", required=False, )
    lg_validity = fields.Char(string="Validity", required=False, )
    lg_amount = fields.Monetary(string='Amount', default=0)
    lg_currency_id = fields.Many2one('res.currency', 'L.G Currency', store=True, )
    lg_currency_rate = fields.Float("L.G Currency Rate", store=True, readonly=True,
                                    help='Ratio between the purchase order currency and the company currency')
    lg_valid_for = fields.Char(string="Valid For", required=False, )
    lg_submitted_from = fields.Char(string="Submitted From", required=False, )
    lg_extension_for = fields.Date(string="LG Extension For", required=False, )

    # fines
    # storage fines
    storage_fees = fields.Monetary(string='Storage Fees', default=0)
    storage_currency_id = fields.Many2one('res.currency', 'Storage Currency', store=True, )
    storage_currency_rate = fields.Float("Storage Currency Rate", store=True, readonly=True,
                                         help='Ratio between the purchase order currency and the company currency')

    # demurrage fines
    demurrage_fees = fields.Monetary(string='Demurrage Fees', default=0)
    demurrage_currency_id = fields.Many2one('res.currency', 'Demurrage Currency', store=True, )
    demurrage_currency_rate = fields.Float("Demurrage Currency Rate", store=True, readonly=True,
                                           help='Ratio between the purchase order currency and the company currency')
    # Delay fines
    delay_penalty = fields.Monetary(string='Delay Penalty', default=0)
    penalty_currency_id = fields.Many2one('res.currency', 'Penalty Currency', store=True, )
    penalty_currency_rate = fields.Float("Penalty Currency Rate", store=True, readonly=True,
                                         help='Ratio between the purchase order currency and the company currency')
    penalty_percentage = fields.Float(string="Penalty Percentage", required=False, default=0)

    payment_fees = fields.Boolean(string="Payment Fees", )
    committed_decision = fields.Char(string="Committed Decision", required=False, )
    committed_decision_date = fields.Date(string="Committed Decision Date", required=False, )

    def unlink(self):
        for order in self:
            if order.state not in ('draft', 'cancel'):
                raise UserError(_('You can not delete a Followup Which Is Not In Draft State.'))
        return super(PurchaseOrderFollowup, self).unlink()

    @api.onchange('purchase_id')
    def _purchase_order_duplicate(self):
        if self.purchase_id:
            records = self.env['purchase.order.followup'].search([('purchase_id', '=', self.purchase_id.id)])
            if len(records) != 0:
                raise UserError(_('There is Already Order Follow-up For this purchase order'))

    @api.model
    def create(self, values):
        if values.get('name', _('New')) == _('New'):
            seq_date = None
            if 'date_followup' in values:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(values['date_followup']))
            if 'company_id' in values:
                values['name'] = self.env['ir.sequence'].with_context(force_company=values['company_id']).next_by_code(
                    'purchase.order.followup', sequence_date=seq_date) or _('New')
            else:
                values['name'] = self.env['ir.sequence'].next_by_code('purchase.order.followup',
                                                                      sequence_date=seq_date) or _('New')

        result = super(PurchaseOrderFollowup, self).create(values)
        return result

    def name_get(self):
        res = []
        for rec in self:
            name = rec.name
            if rec.partner_id.name:
                name = '%s - %s' % (name, rec.partner_id.name)
            res.append((rec.id, name))
        return res

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        if operator == 'ilike' and not (name or '').strip():
            domain = []
        elif operator in ('ilike', 'like', '=', '=like', '=ilike'):
            domain = expression.AND([
                args or [],
                ['|', ('name', operator, name), ('partner_id.name', operator, name)]
            ])
            order_ids = self._search(domain, limit=limit, access_rights_uid=name_get_uid)
            return models.lazy_name_get(self.browse(order_ids).with_user(name_get_uid))
        return super(PurchaseOrderFollowup, self)._name_search(name, args=args, operator=operator, limit=limit,
                                                               name_get_uid=name_get_uid)

    def action_draft(self):
        orders = self.filtered(lambda s: s.state in ['cancel'])
        return orders.write({
            'state': 'draft',
        })

    def action_cancel(self):
        return self.write({'state': 'cancel'})

    def action_done(self):
        return self.write({'state': 'done'})

    def action_approve(self):
        return self.write({'state': 'approve'})
