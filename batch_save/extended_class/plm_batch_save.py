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
Created on 9 Dec 2016

@author: Daniel Smerghetto
'''
import requests
from openerp import models
from openerp import api
from openerp import fields
from openerp import _
from openerp.exceptions import UserError
import logging


class PlmBatchSave(models.Model):
    _name = 'plm.batch_save'

    name = fields.Char(compute='_compute_name', readonly=True)
    file_size = fields.Float(string=_('File Size'), readonly=True)
    document_ids = fields.One2many('plm.document', 'batch_id', string=_('Related Documents'))
    errors_ids = fields.One2many('plm.batch_save_err', 'batch_id', string=_('Errors'))
    active = fields.Boolean(_('Active'), default=True)
    url_for_resave = fields.Text(_('URL For Resave'))

    def _compute_name(self):
        for record in self:
            record.name = '%s' % (record.id)

    @api.model
    def clearBatchRelations(self, batchID):
        # document relations and deactivate batch
        return self.browse(batchID).write({'active': False})

    @api.multi
    def resave_batch(self):
        if not self.url_for_resave:
            raise UserError(_('No saving url found! Cannot re-save!'))
        try:
            requests.post(self.url_for_resave)
        except Exception, ex:
            raise UserError(_('Could not save again from the CAD. Error: %r' % (ex)))
        
PlmBatchSave()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: