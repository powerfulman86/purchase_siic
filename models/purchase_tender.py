# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression


class PurchaseTender(models.Model):
    _name = 'purchase.tender'
    _description = 'Purchase Tender'
    _rec_name = 'name'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']

    name = fields.Char('Name', readonly=True, track_visibility="onchange")
    internal_reference = fields.Char('Reference', readonly=True, states={'draft': [('readonly', False)]}, )

    state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirmed'), ('bid_selection', 'Bid Selection'),
                              ('req_ver_dept', 'Request Verification'), ('verified', 'Verified'),
                              ('gmapproved', 'GM Approved'), ('closed', 'Closed'), ('cancel', 'Cancelled')],
                             string="State", default='draft', track_visibility="onchange")
    rfq_count = fields.Integer("Received Quotations", compute='get_rfq_count')
    order_count = fields.Integer("Selected Orders", compute='get_order_count')
    tender_user_id = fields.Many2one('res.users', 'Representative', track_visibility="onchange",
                                     default=lambda self: self.env.user, readonly=True,
                                     states={'draft': [('readonly', False)]}, )
    tender_type = fields.Many2one('purchase.tender.type', 'Tender Type', required=True,
                                  track_visibility="onchange", readonly=True, states={'draft': [('readonly', False)]}, )
    purchase_request_id = fields.Many2one('purchase.request', 'Purchase Request')
    partner_ids = fields.Many2many('res.partner', string='Vendors', track_visibility="onchange", readonly=True,
                                   states={'draft': [('readonly', False)]}, )
    tender_deadline = fields.Datetime('Tender Deadline', track_visibility="onchange", default=fields.Date.context_today,
                                      readonly=True, states={'draft': [('readonly', False)]}, )
    announce_date = fields.Date('Announce Date', track_visibility="onchange", default=fields.Date.context_today,
                                readonly=True, states={'draft': [('readonly', False)]}, )
    delivery_date = fields.Date('Delivery Date', track_visibility="onchange", default=fields.Date.context_today,
                                readonly=True, states={'draft': [('readonly', False)]}, )
    source = fields.Char('Source Document', track_visibility="onchange")
    dept_note = fields.Char('Department note')
    notes = fields.Text("Terms & Conditions", track_visibility="onchange")
    purchase_tender_line_ids = fields.One2many('purchase.tender.line', 'tender_id', string='Purchase Tender Line',
                                               readonly=True, states={'draft': [('readonly', False)]}, )
    branch_request_count = fields.Integer("Branch Requests", compute='_get_branch_request_count')
    apply_type = fields.Selection(string="Apply Type", selection=[('file', '1 File'), ('two-file', 'Two Files'), ],
                                  required=True, readonly=True, states={'draft': [('readonly', False)]},
                                  default='file')
    technical_file_date = fields.Date('Technical File Date', track_visibility="onchange",
                                      default=fields.Date.context_today,
                                      readonly=True, states={'draft': [('readonly', False)]}, )
    financial_file_date = fields.Date('Financial File Date', track_visibility="onchange",
                                      default=fields.Date.context_today,
                                      readonly=True, states={'draft': [('readonly', False)]}, )

    def name_get(self):
        res = []
        for rec in self:
            name = '[%s] - %s' % (rec.internal_reference, rec.name)
            res.append((rec.id, name))
        return res

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if operator == 'ilike' and not (name or '').strip():
            domain = []
        else:
            domain = ['|', ('name', operator, name), ('internal_reference', operator, name)]
        rec = self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
        return models.lazy_name_get(self.browse(rec).with_user(name_get_uid))

    def unlink(self):
        for order in self:
            if order.state not in ('draft', 'cancel'):
                raise UserError(_('You can not delete a Tender Which Is Not In Draft State.'))
        return super(PurchaseTender, self).unlink()

    @api.model
    def create(self, values):
        if values.get('name', _('New')) == _('New'):
            seq_date = None
            values['name'] = self.env['ir.sequence'].next_by_code('purchase.tender', sequence_date=seq_date) or _('New')
        result = super(PurchaseTender, self).create(values)
        return result

    def _compute_access_url(self):
        super(PurchaseTender, self)._compute_access_url()
        for tender in self:
            tender.access_url = '/my/tender/%s' % (tender.id)

    def _get_report_base_filename(self):
        self.ensure_one()
        return '%s %s' % ('Tender', self.name)

    def get_rfq_count(self):
        if self:
            for rec in self:
                purchase_orders = self.env['purchase.tender.order'].sudo().search(
                    [('tender_id', '=', rec.id), ('selected_order', '=', False)])
                if purchase_orders:
                    rec.rfq_count = len(purchase_orders.ids)
                else:
                    rec.rfq_count = 0

    def get_order_count(self):
        if self:
            for rec in self:
                purchase_orders = self.env['purchase.order'].sudo().search(
                    [('tender_id', '=', rec.id), ('state', 'not in', ['cancel'])])
                if purchase_orders:
                    rec.order_count = len(purchase_orders.ids)
                else:
                    rec.order_count = 0

    def _get_branch_request_count(self):
        if self:
            for rec in self:
                branch_requests = self.env['purchase.branch.req'].sudo().search(
                    [('tender_id', '=', rec.id), ('state', 'not in', ['cancel'])])
                if branch_requests:
                    rec.branch_request_count = len(branch_requests.ids)
                else:
                    rec.branch_request_count = 0

    def action_confirm(self):
        if self:
            for rec in self:
                seq = self.env['ir.sequence'].next_by_code('purchase.tender')
                rec.name = seq
                rec.state = 'confirm'

    def action_new_quotation(self):
        if self:
            for rec in self:
                line_ids = []
                current_date = None
                if rec.delivery_date:
                    current_date = rec.delivery_date
                else:
                    current_date = fields.Datetime.now()
                for rec_line in rec.purchase_tender_line_ids:
                    line_vals = {
                        'product_id': rec_line.product_id.id,
                        'name': rec_line.product_id.name,
                        'date_planned': current_date,
                        'product_qty': rec_line.qty,
                        'status': 'draft',
                        'tender_id': rec.id,
                        'product_uom': rec_line.product_id.uom_id.id,
                        'price_unit': rec_line.price_unit,
                        'currency_rate': 1,
                    }
                    line_ids.append((0, 0, line_vals))
                return {
                    'name': _('New'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'purchase.tender.order',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'context': {'default_tender_id': rec.id,
                                'default_purchase_request_id': rec.purchase_request_id.id,
                                'default_user_id': rec.tender_user_id.id, 'default_order_line': line_ids},
                    'target': 'current'
                }

    def action_validate(self):
        # insert lines in tender lines
        if len(self.purchase_tender_line_ids) == 0:
            raise UserError(_('You Must Select Products For Tender.'))
        if self.rfq_count == 0:
            raise UserError(_('You Must Insert Tender Quotation Orders.'))
        if self:
            for rec in self:
                rec.state = 'bid_selection'

    def action_done(self):
        if self:
            for rec in self:
                rec.state = 'closed'

    def action_analyze_rfq(self):
        list_id = self.env.ref('purchase_siic.tender_bidline_tree_view').id
        form_id = self.env.ref('purchase_siic.tender_bidline_tree_view').id
        return {
            'name': _('Tender Lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.tender.order.line',
            'view_type': 'form',
            'view_mode': 'tree,form,pivot',
            # 'views': [(list_id, 'tree'), (form_id, 'form')],
            'domain': [('tender_id', '=', self.id), ('state', 'not in', ['cancel']),
                       ('order_id.selected_order', '=', False)],
            'context': {'search_default_groupby_product': 1},
            'target': 'current'
        }

    def action_set_to_draft(self):
        if self:
            for rec in self:
                rec.state = 'draft'

    def action_cancel(self):
        if self:
            for rec in self:
                rec.state = 'cancel'

    def action_req_ver_dept(self):
        if self:
            for rec in self:
                rec.state = 'req_ver_dept'

    def action_gm_approved(self):
        if self:
            for rec in self:
                rec.state = 'gmapproved'

    def action_dept_verified(self):
        if self:
            for rec in self:
                rec.state = 'verified'
                self.with_user(self.env.user).message_post(
                    body=self.dept_note, message_type='comment', subtype='mt_comment')

    def action_send_tender(self):
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        template_id = \
            ir_model_data.get_object_reference('purchase_siic', 'email_template_edi_purchase_tedner')[1]
        try:
            compose_form_id = ir_model_data.get_object_reference('mail', 'email_compose_message_wizard_form')[1]
        except ValueError:
            compose_form_id = False
        ctx = {
            'default_model': 'purchase.tender',
            'default_res_id': self.ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'custom_layout': "mail.mail_notification_paynow",
            'force_email': True
        }
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }

    def action_view_quote(self):
        return {
            'name': _('Received Quotations'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.tender.order',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_id': self.id,
            'domain': [('tender_id', '=', self.id), ('selected_order', '=', False)],
            'target': 'current'
        }

    def action_view_order(self):
        return {
            'name': _('Selected Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_id': self.id,
            'domain': [('tender_id', '=', self.id)],
            'target': 'current'
        }

    def action_view_branch_request(self):
        return {
            'name': _('Branch Requests'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.branch.req',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_id': self.id,
            'domain': [('tender_id', '=', self.id)],
            'target': 'current'
        }


class PurchaseTenderLine(models.Model):
    _name = 'purchase.tender.line'
    _description = "Purchase tender Line"

    tender_id = fields.Many2one('purchase.tender', 'Purchase Tender')
    product_id = fields.Many2one('product.product', 'Product', required=True)
    qty = fields.Float('Quantity', default=1.0)
    ordered_qty = fields.Float('Ordered Quantities', compute='get_ordered_qty')
    price_unit = fields.Float('Unit Price')
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')
    product_uom_id = fields.Many2one('uom.uom', string='Product Unit of Measure',
                                     domain="[('category_id', '=', product_uom_category_id)]")
    schedule_date = fields.Date(string='Scheduled Date')

    def get_ordered_qty(self):
        if self:
            for rec in self:
                order_qty = 0.0
                purchase_order_lines = self.env['purchase.tender.order.line'].sudo().search(
                    [('product_id', '=', rec.product_id.id), ('tender_id', '=', rec.tender_id.id),
                     ('order_id.selected_order', '=', True), ('order_id.state', 'in', ['purchase'])])
                for line in purchase_order_lines:
                    order_qty += line.product_qty
                rec.ordered_qty = order_qty


class PurchaseTenderType(models.Model):
    _name = 'purchase.tender.type'
    _description = 'Purchase Tender Type'
    _rec_name = 'name'

    name = fields.Char("Name", required=True)
    notes = fields.Text(string="Notes", required=False, )
    active = fields.Boolean('Active', default=True)
