# -*- coding: utf-8 -*-

from odoo import api, models, fields

class UsersInherit(models.Model):
    _inherit = "res.users"

    mobile = fields.Char(string='Mobile')