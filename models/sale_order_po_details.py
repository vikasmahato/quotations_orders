
from odoo import models, fields, api,_
from odoo.exceptions import UserError

class SaleOrderPoDetails(models.Model):
    _name='sale.order.po.details'
    _description='sale.order.po.details'

    sale_order_id = fields.Many2one('sale.order', string='Export', index=True, ondelete='cascade')

    po_number = fields.Char(string='PO Number')
    po_amount = fields.Char(string='PO Amount')
    po_date = fields.Date(string='PO Date')
    pickup_date = fields.Date(string='Pickup Date')
    rental_order = fields.Binary(string="Rental Order")

    @api.model
    def create(self, vals):
        try:
            if 'sale_order_id' not in vals:
                vals['sale_order_id'] = self.env.context.get('default_sale_order_id')
                sale_order = self.env['sale.order'].browse(vals['sale_order_id'])

                # Update the PO details records
                sale_order.write({
                    'po_number': vals.get('po_number', sale_order.po_number),
                    'po_amount': vals.get('po_amount', sale_order.po_amount),
                    'po_date': vals.get('po_date', sale_order.po_date),
                    'pickup_date': vals.get('pickup_date', sale_order.pickup_date),
                    'rental_order': vals.get('rental_order', sale_order.rental_order),
                })

                sale_order.action_extend()
            return super(SaleOrderPoDetails, self).create(vals)

        except Exception as e:
            raise UserError(_(e))
