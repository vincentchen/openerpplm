# -*- encoding: utf-8 -*-
##############################################################################
#
#    OmniaSolutions, Open Source Management Solution    
#    Copyright (C) 2010-2011 OmniaSolutions (<http://www.omniasolutions.eu>). All Rights Reserved
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
Created on Mar 24, 2016

@author: Daniel Smerghetto
'''
from openerp.osv import osv, fields
import logging


class ComponentExtension(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'


    def NewRevision(self, cr, uid, ids, context=None):
        """
            create a new revision of current component
        """
        dictToRewrite = {}
        bomObj = self.pool.get('mrp.bom')
        bom_ids = bomObj.search(cr, uid, [('product_id','in',ids), ('type','=','ebom')])
        for bom_id in bom_ids:
            bomLineList = []
            bomBrws = bomObj.browse(cr, uid, bom_id)
            for bomLineBrws in bomBrws.bom_line_ids:
                if not bomLineBrws.source_id:
                    bomLineList.append({'product_uom': bomLineBrws.product_uom.id, 'product_id': bomLineBrws.product_id.id, 'product_qty': bomLineBrws.product_qty, 'type':bomLineBrws.type})
            if bomLineList:
                dictToRewrite[bom_id] = bomLineList
        newID, newIndex = super(ComponentExtension, self).NewRevision(cr, uid, ids, context=context)
        newIndex
        new_component_brws = self.browse(cr, uid, newID)
        for bom_id, bomLines in dictToRewrite.items():
            defaultVals = {'product_tmpl_id': new_component_brws.product_tmpl_id.id,  'product_id': newID, 'bom_line_ids': []}
            new_bom_id = bomObj.copy(cr, uid, bom_id, defaults=defaultVals)
            for lineVals in bomLines:
                bomObj.write(cr, uid, new_bom_id, {'bom_line_ids': [(0, 0, lineVals)]})
        return (newID, newIndex)
    
ComponentExtension()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: