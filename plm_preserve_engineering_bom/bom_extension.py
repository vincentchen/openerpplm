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


class BomExtension(osv.osv):
    _name = 'mrp.bom'
    _inherit = 'mrp.bom'
    
    def SaveStructure(self, cr, uid, relations, level=0, currlevel=0):
        def getBomLinesToReWrite(relations):
            """
                Processes relations  
            """
            dictToRewrite = {}
            for parentName, parentProductID, tmpChildName, tmpChildID, sourceID, tempRelArgs in relations:
                parentName, tmpChildName, tmpChildID, tempRelArgs, sourceID
                if parentProductID:
                    bomLineList = []
                    bom_ids = self.search(cr,uid,[('product_id','=',parentProductID), ('type','=','ebom')])
                    print 'bom_ids : ' + str(bom_ids)
                    for bom_id in bom_ids:
                        bomBrws = self.browse(cr, uid, bom_id)
                        for bomLineBrws in bomBrws.bom_line_ids:
                            if not bomLineBrws.source_id:
                                bomLineList.append({'product_uom': bomLineBrws.product_uom.id, 'product_id': bomLineBrws.product_id.id, 'product_qty': bomLineBrws.product_qty})
                        self.unlink(cr, uid, [bom_id])
                    if bomLineList:
                        dictToRewrite[parentProductID] = bomLineList
            return dictToRewrite

        dictToRewrite = getBomLinesToReWrite(relations)
        super(BomExtension, self).SaveStructure(cr, uid, relations, level=level, currlevel=currlevel)
        print dictToRewrite
        for parentProductID, bomLineList in dictToRewrite.items():
            bom_ids = self.search(cr,uid,[('product_id','=',parentProductID), ('type','=','ebom')])
            if not bom_ids:
                raise osv.except_osv(_('Bom not found.'), _('No  bom found for product_id: %s' % parentProductID))
            for bom_id in bom_ids:
                for bomLineVals in bomLineList:
                    res = self.write(cr, uid, bom_id, {'bom_line_ids': [(0, 0, bomLineVals)]})
                    if not res:
                        message = "BoM Line not wrote with vals %r." %(bomLineVals)
                        logging.warning(message)
                        raise osv.except_osv(_('Creating a new Bom Line Object.'), _(message))
        return False

BomExtension()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: