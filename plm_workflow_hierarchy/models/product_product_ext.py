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
Created on 22 Aug 2016

@author: Daniel Smerghetto
'''
from openerp.exceptions import UserError
from openerp import models
from openerp import osv
from openerp import fields
from openerp import api
from openerp import _
import logging


class ProductProductExtension(models.Model):
    _inherit = 'product.product'
    
    @api.multi
    def action_draft_multiple(self):
        excludeStatuses = ['draft','released','undermodify','obsoleted']
        includeStatuses = ['confirmed','transmitted']
        for prodBrws in self:
            userErrors, idsToBeChanged = prodBrws._get_recursive_parts(excludeStatuses, includeStatuses)
            if userErrors:
                raise UserError(userErrors)
            return {
                'type': 'ir.actions.act_window',
                'name': _('Product To be set in draft state'),
                'view_type': 'form',
                'target': 'new',
                'view_mode': 'form',
                #'view_id': self.env.ref('plm_workflow_hierarchy.plm_component_draft_multiple'),
                'res_model': 'product.workflow_draft',
                'context': {'default_draft_components': idsToBeChanged},
            }


class ProductProductExtended(osv.osv.osv_memory):
    _name = 'product.workflow_draft'

    draft_components = fields.Many2many('product.product', 'workflow_wizard_plm_component_rel', 'wkf_wizard_id', 'component_id', string=_("Component to be set in draft mode"))

    @api.multi
    def setMultipleToDraft(self):
        defaults = {}
        status = 'draft'
        signal = 'correct'
        defaults['engineering_writable'] = True
        defaults['state'] = status
        for wizardBrws in self:
            for compBrws in wizardBrws.draft_components:
                compBrws._action_ondocuments(status)
                compBrws.signal_workflow(signal)
                res = compBrws.product_tmpl_id.write(defaults)
                if res:
                    compBrws.wf_message_post(body=_('Status moved to: %s.' % (_('Draft'))))
        return True


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
