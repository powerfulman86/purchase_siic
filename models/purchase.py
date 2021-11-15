# -*- coding: utf-8 -*-


from odoo import api, fields, models, SUPERUSER_ID, _


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    order_type = fields.Selection(string="Type", selection=[('in', 'Local'), ('out', 'Foreign'), ], required=True,
                                  tracking=1, default='in')
    order_no = fields.Integer(string="Order Number", required=True, index=True, digits=(8, 0))
    tender_id = fields.Many2one('purchase.tender', 'Purchase Tender')
    tender_state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirmed'), ('bid_selection', 'Bid Selection'),
                                     ('req_ver_dept', 'Request Verification'), ('verified', 'Verified'),
                                     ('gmapproved', 'GM Approved'), ('closed', 'Closed'), ('cancel', 'Cancelled')],
                                    string="Tender State", default='draft', related="tender_id.state", store=True)
    payment_type = fields.Many2one("purchase.payment.type", string="Payment Type", )
    delivery_time = fields.Many2one("purchase.delivery.time", string="Delivery Time", )
    final_guarantee = fields.Selection(string="Final Guarantee",
                                       selection=[('exist', 'Exist'), ('notexist', 'Not Exist'),
                                                  ('reserved', 'Reserved')], required=False, )
    follow_up = fields.One2many(comodel_name="purchase.order.followup", inverse_name="purchase_id", string="Follow-Up",
                                required=False, )
    msg = fields.Char("Message", compute='_compute_msg')

    def action_view_followup(self):
        self.ensure_one()
        records = self.env['purchase.order.followup'].search([('purchase_id', '=', self.id)])
        if len(records.ids) == 0:
            record = {
                'purchase_id': self.id,
                'partner_id': self.partner_id.id,
            }
            self.env['purchase.order.followup'].create(record)

        return {
            "type": "ir.actions.act_window",
            'res_model': 'purchase.order.followup',
            "views": [[False, "form"]],
            "res_id": self.follow_up.id,
            "context": {"create": False},
        }

    @api.depends('partner_id')
    def _compute_msg(self):
        if self:
            for rec in self:
                rec.msg = ''
                if rec.agreement_id and rec.partner_id.id not in rec.agreement_id.partner_ids.ids:
                    rec.msg = 'Vendor you have selected not exist in selected tender. You can still create quotation for that.'


class ShPurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    tender_id = fields.Many2one('purchase.tender', 'Purchase Tender', related='order_id.tender_id', store=True)
    tender_state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirmed'), ('bid_selection', 'Bid Selection'),
                                     ('req_ver_dept', 'Request Verification'), ('verified', 'Verified'),
                                     ('gmapproved', 'GM Approved'), ('closed', 'Closed'), ('cancel', 'Cancelled')],
                                    string="Tender State", default='draft', related="tender_id.state", store=True)
