from odoo import models, fields, api, _
from odoo import tools

class VehicleType(models.Model):
    _name = 'vehicle.type'
    _description = 'Vehicle Type'

    currency_id = fields.Many2one("res.currency", string="Currency id ",defualt=20,invisible=True)

    cft = fields.Integer(string="CFT")
    vehicle_type = fields.Char(string="Vehicle Type")
    minimum_km_one_side = fields.Integer(string="Minimum Km One Side")
    rates_per_km = fields.Monetary(string="Rates Per Km", default=0.0, currency_field='currency_id')
    minimum_km_one_side_prices = fields.Monetary(string="Minimum Km One Side Prices", default=0.0, currency_field='currency_id')

    @api.model
    def get_vehicle_types_sorted_by_cft(self):
        # Use search() to retrieve all records and sort them by the 'cft' field.
        vehicle_types = self.search([])  # Retrieve all records
        sorted_vehicle_types = sorted(vehicle_types, key=lambda x: x.cft)  # Sort by 'cft'
        return sorted_vehicle_types
