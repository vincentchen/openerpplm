# -*- encoding: utf-8 -*-
##############################################################################
#
#    OmniaSolutions, Your own solutions
#    Copyright (C) 2010 OmniaSolutions (<http://omniasolutions.eu>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
'''
Created on Mar 15, 2017

@author: daniel
'''
from openerp import models
from openerp import api
from openerp import fields
from openerp import _
import logging


class PlmDocument(models.Model):
    _inherit = 'plm.document'

    batch_id = fields.Many2one('plm.batch_save', string=_('Related Batch'))

PlmDocument()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
