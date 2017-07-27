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
from openerp import fields
from openerp import api
from openerp import _
import logging


class ProductProductExtended(models.Model):
    _name = 'product.rev_wizard'
    reviseDocument = fields.Boolean(_('Document Revision'), help=_("""Make new revision of the linked document"""))
    reviseNbom = fields.Boolean(_('Normal Bom Revision'), help=_("""Make new revision of the linked Normal BOM"""))
    reviseSbom = fields.Boolean(_('Spare Bom Revision'), help=_("""Make new revision of the linked Spare BOM"""))
    reviseEbom = fields.Boolean(_('Engineering Bom Revision'), help=_("""Make new revision of the linked Engineering BOM.
                                                                      Note that only lines without source ID are copied to
                                                                      new bom revision."""))

    @api.multi
    def action_create_new_revision_by_server(self):
        product_id = self.env.context.get('default_product_id', False)
        if not product_id:
            logging.error('[action_create_new_revision_by_server] Cannot revise because product_id is %r' % (product_id))
            raise UserError(_('Current component cannot be revised!'))
        prodProdEnv = self.env['product.product']
        prodBrws = prodProdEnv.browse(product_id)
        if self.stateAllows(prodBrws, 'Component'):
            revRes = prodBrws.NewRevision()
            newID, newIndex = revRes
            newIndex
            if not newID:
                logging.error('[action_create_new_revision_by_server] newID: %r' % (newID))
                raise UserError(_('Something wrong happens during new component revision process.'))
            if self.reviseDocument:
                self.docRev(prodBrws, newID, prodProdEnv)
            if self.reviseNbom:
                self.commonBomRev(prodBrws, newID, prodProdEnv, 'normal')
            if self.reviseSbom:
                self.commonBomRev(prodBrws, newID, prodProdEnv, 'spbom')
            if self.reviseEbom:
                self.ebomRevision(prodBrws, newID, prodProdEnv)
            return {'name': _('Revised Product'),
                    'view_type': 'tree,form',
                    "view_mode": 'form',
                    'res_model': 'product.product',
                    'res_id': newID,
                    'type': 'ir.actions.act_window'}

    @api.multi
    def stateAllows(self, brwsObj, objType):
        if brwsObj.state != 'released':
            logging.error('[action_create_new_revision_by_server:stateAllows] Cannot revise obj %s, Id: %r because state is %r' % (objType, brwsObj.id, brwsObj.state))
            raise UserError(_("%s cannot be revised because the state isn't released!" % (objType)))
        return True

    @api.multi
    def docRev(self, prodBrws, newID, prodProdEnv):
        docRelObj = self.env['plm.document.relation']
        plmDocObj = self.env['plm.document']
        newDocumentIds = []
        browsModelsDict = {}        # {oldModelBrws: newModelBrws}
        modelsDocumentsDict = {}    # {oldModelBrws: [newChildrenDocBrws]}
        for docBrws in prodBrws.linkeddocuments:
            if self.stateAllows(docBrws, 'Document'):
                resDoc = docBrws.NewRevision()
                newDocID, _newDocIndex = resDoc
                newDocBrws = plmDocObj.browse(newDocID)
                if not newDocID:
                    logging.error('[action_create_new_revision_by_server] newDocID: %r' % (newDocID))
                    raise UserError(_('Something wrong happens during new document revision process.'))
                relRes = docRelObj.search([('link_kind', '=', 'LyTree'), ('parent_id', '=', docBrws.id)])
                if relRes:
                    browsModelsDict[docBrws] = newDocBrws
                else:
                    for relObj in docRelObj.search([('link_kind', '=', 'LyTree'), ('child_id', '=', docBrws.id)]):
                        if relObj.parent_id in modelsDocumentsDict:
                            modelsDocumentsDict[relObj.parent_id].append(newDocBrws)
                        else:
                            modelsDocumentsDict[relObj.parent_id] = [newDocBrws]
                newDocumentIds.append(newDocID)
        prodProdEnv.browse(newID).linkeddocuments = newDocumentIds
        self.repairDocRelations(prodBrws, browsModelsDict, modelsDocumentsDict, docRelObj)

    @api.multi
    def repairDocRelations(self, oldProdBrws, browsModelsDict, modelsDocumentsDict, docRelObj):
        for oldBrwsModel, newBrwsModel in browsModelsDict.items():
            for newDocChildBrws in modelsDocumentsDict.get(oldBrwsModel, []):
                docRelObj.create({'link_kind': 'LyTree',
                                  'child_id': newDocChildBrws.id,
                                  'parent_id': newBrwsModel.id,
                                  }
                                 )
                docRelObj.create({'link_kind': 'HiTree',
                                  'child_id': newBrwsModel.id,
                                  'parent_id': newDocChildBrws.id,
                                  }
                                 )

    @api.multi
    def ebomRevision(self, oldProdBrws, newID, prodProdEnv):
        bomObj = self.env['mrp.bom']
        newProdBrws = prodProdEnv.browse(newID)
        for bomBrws in bomObj.search([('product_tmpl_id', '=', oldProdBrws.product_tmpl_id.id), ('type', '=', 'ebom')]):
            newBomBrws = bomBrws.copy()
            newbomLines = []
            newBomBrws.product_tmpl_id = newProdBrws.product_tmpl_id.id
            for oldBomLineBrws in bomBrws.bom_line_ids:
                if not oldBomLineBrws.source_id:
                    newbomLines.append(oldBomLineBrws.copy().id)
            newBomBrws.write({'bom_line_ids': [(6, '', newbomLines)]})

    @api.multi
    def commonBomRev(self, oldProdBrws, newID, prodProdEnv, bomType):
        bomObj = self.env['mrp.bom']
        newProdBrws = prodProdEnv.browse(newID)
        for bomBrws in bomObj.search([('product_tmpl_id', '=', oldProdBrws.product_tmpl_id.id), ('type', '=', bomType)]):
            newBomBrws = bomObj.copy(bomBrws.id)
            newBomBrws.product_tmpl_id = newProdBrws.product_tmpl_id.id
            # Commented because source ID at the moment is not fixable
#             if bomType == 'ebom':
#                 self.repairSourceId(newBomBrws, bomBrws)

    @api.model
    def repairSourceId(self, newBom, oldBom):
        """
        upgrade the source id at the new version
        """
        pass
        # TODO: finish this
        for objDoc in self.env['plm.document'].browse(oldBom.source_id):
            args = {'name': objDoc.name,
                    'revisionid': objDoc .revisionid}
            newId = self.env['plm.document'].GetLatestIds(args)

ProductProductExtended()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
