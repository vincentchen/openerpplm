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
from openerp.exceptions import UserError

'''
Created on 9 Dec 2016

@author: Daniel Smerghetto
'''

from openerp import models
from openerp import api
from openerp import fields
from openerp import _
from openerp.exceptions import UserError
import logging


class PlmCheckout(models.Model):
    _name = 'plm.checkout'
    _inherit = 'plm.checkout'
    
    batch_save_id = fields.Many2one('plm.batch_save', string=_('Related Batch Save'))

    @api.multi
    def unlink(self):
        for checkoutBrws in self:
            docBrws = checkoutBrws.documentid
            if docBrws.batch_id:
                raise UserError(_('A batch save is already linked to the document %r and revision %r. You cannot check-in.' % (docBrws.name, docBrws.revisionid)))
        return super(PlmCheckout, self).unlink()

PlmCheckout()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: