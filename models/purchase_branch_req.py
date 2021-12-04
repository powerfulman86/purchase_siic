# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang


class PurchaseBranchReq(models.Model):
    _name = 'purchase.branch.req'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']
    _description = 'Purchase Branch Request'
    _order = 'id desc'

    name = fields.Char(string='Request Reference', required=True, copy=False, readonly=True,
                       states={'draft': [('readonly', False)]}, index=True, default=lambda self: _('New'))
    internal_reference = fields.Char(string="Reference", required=False, readonly=True,
                                     states={'draft': [('readonly', False)]}, )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approve', 'Approved'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True, tracking=3, default='draft')

    user_id = fields.Many2one(
        'res.users', string='Purchase Person', index=True, tracking=2, default=lambda self: self.env.user)
    date_request = fields.Date(string='Request Date', readonly=True, copy=False,
                               states={'draft': [('readonly', False)]}, default=fields.Date.context_today)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id.id)
    note = fields.Text('Terms and conditions')
    request_line = fields.One2many('purchase.branch.req.line', 'request_id', string='Branch Purchase Request Lines',
                                   states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=True,
                                   auto_join=True)
    branch_id = fields.Many2one(comodel_name="res.branch", string="Branch", required=True,
                                index=True, tracking=1, readonly=True, states={'draft': [('readonly', False)]}, )
    tender_id = fields.Many2one('purchase.tender', 'Purchase Tender', readonly=True, domain=[('state', '=', 'confirm')],
                                states={'approve': [('readonly', False)]})
    tender_state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirmed'), ('bid_selection', 'Bid Selection'),
                                     ('req_ver_dept', 'Request Verification'), ('verified', 'Verified'),
                                     ('gmapproved', 'GM Approved'), ('closed', 'Closed'), ('cancel', 'Cancelled')],
                                    string="Tender State", default='draft', related="tender_id.state", store=True)

    def unlink(self):
        for order in self:
            if order.state not in ('draft', 'cancel'):
                raise UserError(_('You can not delete a Branch Request Which Is Not In Draft State.'))
        return super(PurchaseBranchReq, self).unlink()

    @api.model
    def create(self, values):
        if values.get('name', _('New')) == _('New'):
            seq_date = None
            if 'date_request' in values:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(values['date_request']))
            if 'company_id' in values:
                values['name'] = self.env['ir.sequence'].with_context(force_company=values['company_id']).next_by_code(
                    'purchase.branch.req', sequence_date=seq_date) or _('New')
            else:
                values['name'] = self.env['ir.sequence'].next_by_code('purchase.branch.req',
                                                                      sequence_date=seq_date) or _('New')

        result = super(PurchaseBranchReq, self).create(values)
        return result

    def action_draft(self):
        orders = self.filtered(lambda s: s.state in ['cancel'])
        return orders.write({'state': 'draft', })

    def action_cancel(self):
        return self.write({'state': 'cancel'})

    def action_done(self):
        # insert lines in tender lines
        if len(self.request_line) == 0:
            raise UserError(_('You Must Select Products For Request.'))

        if not self.tender_id:
            raise UserError(_('Purchase Tender Must Be Selected Before Processing.'))

        if self.tender_id and self.tender_state == 'confirm' and len(self.request_line) != 0:
            for rec in self.request_line:
                check_product = self.env['purchase.tender.line'].sudo().search(
                    [('product_id', '=', rec.product_id.id), ('tender_id', '=', self.tender_id.id)],
                    limit=1)
                if len(check_product) != 0:
                    check_product.qty += rec.product_uom_qty
                else:
                    line_vals = {
                        'tender_id': self.tender_id.id,
                        'product_id': rec.product_id.id,
                        'product_uom_id': rec.product_id.uom_id.id,
                        'qty': rec.product_qty,
                    }
                    self.env['purchase.tender.line'].sudo().create(line_vals)
        return self.write({'state': 'done'})

    def action_approve(self):
        if len(self.request_line) == 0:
            raise UserError(_('You Must Select Products For Request.'))

        return self.write({'state': 'approve'})


class PurchaseBranchReqLine(models.Model):
    _name = 'purchase.branch.req.line'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']
    _description = 'Purchase Branch Request Line'
    _order = 'id desc'

    request_id = fields.Many2one('purchase.branch.req', string='Branch Purchase Request', required=False,
                                 ondelete='cascade', index=True, copy=False)
    name = fields.Text(string='Description', )
    sequence = fields.Integer(string='Sequence', default=10)
    product_id = fields.Many2one('product.product', string='Product', required=1,
                                 domain="[('purchase_ok', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
                                 change_default=True, ondelete='restrict', check_company=True)  # Unrequired company
    product_template_id = fields.Many2one('product.template', string='Product Template',
                                          related="product_id.product_tmpl_id", domain=[('purchase_ok', '=', True)])
    product_updatable = fields.Boolean(string='Can Edit Product', readonly=True, default=True)
    product_qty = fields.Float(string='Quantity', digits='Product Unit of Measure', required=True)
    product_uom_qty = fields.Float(string='Total Quantity', compute='_compute_product_uom_qty', store=True)
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure',
                                  domain="[('category_id', '=', product_uom_category_id)]")
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id', readonly=True)
    date_request = fields.Date(related='request_id.date_request', string='Request Date', readonly=True)
    branch_id = fields.Many2one(comodel_name="res.branch", related='request_id.branch_id', string="Branch",
                                required=True, index=True, tracking=1, )

    company_id = fields.Many2one(comodel_name='res.company', related='request_id.company_id', required=True, )

    @api.onchange('product_id')
    def onchange_product_id(self):
        if not self.product_id:
            return

        # Reset date, price and quantity since _onchange_quantity will provide default values
        self._product_id_change()
        self._onchange_quantity()

    def _product_id_change(self):
        if not self.product_id:
            return
        product_lang = self.product_id.with_context(
            lang=get_lang(self.env).code,
            company_id=self.company_id.id,
        )
        self.name = self._get_product_purchase_description(product_lang)
        self.product_uom = self.product_id.uom_po_id or self.product_id.uom_id

    @api.depends('product_uom', 'product_qty', 'product_id.uom_id')
    def _compute_product_uom_qty(self):
        for line in self:
            if line.product_id and line.product_id.uom_id != line.product_uom:
                line.product_uom_qty = line.product_uom._compute_quantity(line.product_qty, line.product_id.uom_id)
            else:
                line.product_uom_qty = line.product_qty

    @api.onchange('product_qty', 'product_uom')
    def _onchange_quantity(self):
        if not self.product_id:
            return

    def _get_product_purchase_description(self, product_lang):
        self.ensure_one()
        name = product_lang.display_name
        if product_lang.description_purchase:
            name += '\n' + product_lang.description_purchase

        return name
