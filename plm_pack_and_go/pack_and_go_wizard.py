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
import json
from __builtin__ import False
'''
Created on Mar 30, 2016

@author: Daniel Smerghetto
'''
import logging
from openerp import models
from openerp import fields
from openerp import api
from openerp import _
from openerp import osv
from openerp import report
from openerp import tools
from openerp.exceptions import UserError
import os
import base64
import shutil
import requests
_logger = logging.getLogger(__name__)


class AvailableTypes(models.Model):
    _name = 'pack_and_go_types'

    name = fields.Char(_('Name'))
    pack_and_go_view_id = fields.Many2one('pack_and_go_view')


class AdvancedPackView(osv.osv.osv_memory):
    _name = 'pack_and_go_view'

    @api.model
    def _getComponentDescription(self):
        for row in self:
            row.comp_description = row.component_id.description

    @api.model
    def _getDocumentDescription(self):
        for row in self:
            row.document_description = row.document_id.description

    @api.model
    def _getDocumentFileName(self):
        for row in self:
            row.doc_file_name = row.document_id.datas_fname
        
    component_id = fields.Many2one('product.product', _('Component'))
    document_id = fields.Many2one('plm.document', _('Document'))
    comp_rev = fields.Integer(_('Component Revision'))
    comp_description = fields.Char(compute='_getComponentDescription')
    doc_rev = fields.Integer(_('Document Revision'))
    document_description = fields.Char(compute='_getDocumentDescription')
    doc_file_name = fields.Char(compute='_getDocumentFileName')
    preview = fields.Binary(_('Preview Content'))
    # Don't change keys because are used in a lower check in this file
    doc_type = fields.Selection([('2d', _('2D')),
                                 ('3d', _('3D')),
                                 ('pdf', _('PDF')),
                                 ], _('Document Type'))
    available_types = fields.Many2one('pack_and_go_types', _('Types'))
    pack_and_go_id = fields.Many2one('pack.and_go', _('Pack and go id'))


class PackAndGo(osv.osv.osv_memory):
    _name = 'pack.and_go'
    _inherit = 'ir.attachment'

    def setComponentFromContext(self):
        """
            set the default value from getting the value from the context
        """
        return self._context.get('active_id', 0)

    component_id = fields.Many2one('product.product',
                                   _('Component'),
                                   default=setComponentFromContext,
                                   required=True)
    name = fields.Char('Attachment Name',
                       required=True,
                       default=' ')
    type = fields.Selection([('url', 'URL'),
                             ('binary', 'File')],
                            'Type',
                            help="You can either upload a file from your computer or copy/paste an internet link to your file",
                            required=True,
                            change_default=True,
                            default='binary')
    export_type = fields.Selection([('2d', _('2D')),
                                    ('3d', _('3D')),
                                    ('pdf', _('PDF')),
                                    ('2dpdf', _('2D + PDF')),
                                    ('3dpdf', _('3D + PDF')),
                                    ('3d2d', _('3D + 2D')),
                                    ('all', _('2D + 3D + PDF')),
                                    ], _('Export Type'), default='all')
    export_3d = fields.Many2many('pack_and_go_view', 'export3d_pack', 'pack_view_id', 'pack_and_go_id', _('Select Rows to export'))
    export_2d = fields.Many2many('pack_and_go_view', 'export2d_pack', 'pack_view_id', 'pack_and_go_id', _('Select Rows to export'))
    export_pdf = fields.Many2many('pack_and_go_view', 'exportpdf_pack', 'pack_view_id', 'pack_and_go_id', _('Select Rows to export'))
    export_other = fields.Many2many('pack_and_go_view', 'exportother_pack', 'pack_view_id', 'pack_and_go_id', _('Select Rows to export'))

    force_types_3d = fields.Many2one('pack_and_go_types', _('Force Types'))
    force_types_2d = fields.Many2one('pack_and_go_types', _('Force Types'))


    @api.multi
    def computeExportRelField(self, forceType=False):
        '''
            Populate related field with all components and documents of Bill of Materials
        '''
        self.clearAll()
        # Local colletions of ids, necessary to write in related fields
        export_2d = []
        export_3d = []
        export_other = []
        export_pdf = []
        
        checkedDocumentIds = [] # To know if the same document has been already analyzed
        objProduct = self.env['product.product']
        objPackView = self.env['pack_and_go_view']

        def docCheckCreate(doc, comp=False):
            compId = False
            compRev = False
            if comp:
                compId = comp.id
                compRev = comp.engineering_revision
            singleCreateDict = {'component_id': compId,
                                'comp_rev': compRev,
                                'doc_rev': doc.revisionid,
                                'document_id': doc.id,
                                'preview': doc.preview,
                                'available_types': False,
                                'doc_type': doc.document_type,
                                }
            if doc.document_type == '2d':
                if self.export_type in ('2d', '2dpdf', '3d2d', 'all'):
                    newViewObj = objPackView.create(singleCreateDict)
                    export_2d.append(newViewObj.id)
                if self.export_type in ('2dpdf', 'pdf', '3dpdf', 'all'):
                    singleCreateDict['doc_type'] = 'pdf'
                    newViewObj = objPackView.create(singleCreateDict)
                    export_pdf.append(newViewObj.id)
            elif doc.document_type == '3d':
                if self.export_type in ('3d', '3dpdf', '3d2d', 'all'):
                    newViewObj = objPackView.create(singleCreateDict)
                    export_3d.append(newViewObj.id)
            else:
                newViewObj = objPackView.create(singleCreateDict)
                export_other.append(newViewObj.id)

        def recursionDocuments(docBrws):
            docBrwsList = self.getDocumentsByLinks(docBrws)
            for docBrws2 in docBrwsList:
                if docBrws2.id in checkedDocumentIds:
                    continue
                checkedDocumentIds.append(docBrws2.id)
                docCheckCreate(docBrws2)
                recursionDocuments(docBrws2)
            
        self.getAllAvailableTypes() # Setup available types
        compIds = self.getBomCompIds()
        for compBrws in objProduct.browse(compIds):
            for docBrws in compBrws.linkeddocuments:
                if docBrws.id in checkedDocumentIds:
                    continue
                checkedDocumentIds.append(docBrws.id)
                docCheckCreate(docBrws, compBrws)
                recursionDocuments(docBrws)

        self.export_2d = export_2d
        self.export_3d = export_3d
        self.export_other = export_other
        self.export_pdf = export_pdf
        return self.returnWizard()

    @api.multi
    def getDocumentsByLinks(self, docBrws):
        docId = docBrws.id
        docRelObj = self.env['plm.document.relation']
        docRels = docRelObj.search([
                                    '|',
                                    ('parent_id', '=', docId),
                                    ('child_id', '=', docId),
                                    ])
        outBrwsList = []
        for relation in docRels:
            parenBrws = relation.parent_id
            childBrws = relation.child_id
            if parenBrws not in outBrwsList and parenBrws.id != docId:
                outBrwsList.append(parenBrws)
            if childBrws not in outBrwsList and childBrws.id != docId:
                outBrwsList.append(childBrws)
        return outBrwsList

    @api.multi
    def returnWizard(self):
        return {'name': _('Pack and Go'),
                'view_type': 'form',
                "view_mode": 'form',
                'res_model': 'pack.and_go',
                'target': 'new',
                'res_id': self.ids[0],
                'type': 'ir.actions.act_window',
                'domain': "[]"}
        
    @api.multi
    def clear2d(self):
        self.write({'export_2d': [(5, 0, 0)]})
        return self.returnWizard()

    @api.multi
    def clear3d(self):
        self.write({'export_3d': [(5, 0, 0)]})
        return self.returnWizard()

    @api.multi
    def clearpdf(self):
        self.write({'export_pdf': [(5, 0, 0)]})
        return self.returnWizard()

    @api.multi
    def clearother(self):
        self.write({'export_other': [(5, 0, 0)]})
        return self.returnWizard()
               
    @api.multi
    def clearAll(self):
        '''
            Clear all pack and go views
        '''
        packAndGoViewObj = self.env['pack_and_go_view']
        objBrwsList = packAndGoViewObj.search([])
        objBrwsList.unlink()

    def getAllAvailableTypes(self):
        '''
            Read from flask server and create all needed extensions
        '''
        typesObj = self.env['pack_and_go_types']

        def checkCreateType(typeStr):
            res = typesObj.search([('name', '=', typeStr)])
            if not res:
                typesObj.create({'name': typeStr})
        
        # Read from flask server
        serverAddress = self.env['ir.config_parameter']._get_param('Flask server Address')
        fileExtensionsRes = requests.get(serverAddress + '/odooplm/api/v1.0/getAvailableExtention')
        res = json.loads(fileExtensionsRes.content)
        
        # Create all extensions
        for fileExtension, tupleConversion in res.items():
            checkCreateType(fileExtension)
            for ext in tupleConversion[-1]:
                checkCreateType(ext)
        return res

    def getBomFromTemplate(self, prodTmpl):
        bomBrwsList = prodTmpl.bom_ids
        for bomBrws in bomBrwsList:
            if bomBrws.type == 'ebom':
                return [bomBrws]
        if bomBrwsList:
            return [bomBrwsList[0]]
        return []

    def getBomCompIds(self):
        '''
            Get all components composing the Bill of Materials
        '''
        def recursion(bomBrwsList):
            outCompIds = []
            for bomBrws in bomBrwsList:
                for bomLineBrws in bomBrws.bom_line_ids:
                    prodId = bomLineBrws.product_id.id
                    if prodId in outCompIds:
                        continue
                    prodTmplBrws = bomLineBrws.product_id.product_tmpl_id
                    bomBrwsList = self.getBomFromTemplate(prodTmplBrws)
                    lowLevelCompIds = recursion(bomBrwsList)
                    outCompIds.extend(lowLevelCompIds)
                    outCompIds.append(prodId)
            return list(set(outCompIds))

        startingBom = self.getBomFromTemplate(self.component_id.product_tmpl_id)
        if not startingBom:
            return [self.component_id.id]
        compIds = recursion(startingBom)
        compIds.append(self.component_id.id)
        return compIds

    def generateTmpFolder(self):
        '''
            Create temporary folder
        '''
        tmpSubFolder = tools.config.get('document_path', os.path.join(tools.config['root_path'], 'filestore'))
        logging.info("Pack Go sub folder is %r" % tmpSubFolder)
        tmpSubSubFolder = os.path.join(tmpSubFolder, 'export', self.component_id.engineering_code)
        if not os.path.exists(tmpSubSubFolder):
            os.makedirs(tmpSubSubFolder)
        return tmpSubFolder, tmpSubSubFolder

    @api.multi
    def action_export_zip(self):
        """
            action to import the data
        """
        def checkCreateFolder(path):
            if not os.path.exists(path):
                os.makedirs(path, 0777)
            
        tmpSubFolder, tmpSubSubFolder = self.generateTmpFolder()
        export_zip_folder = os.path.join(tmpSubFolder, 'export_zip')
        checkCreateFolder(export_zip_folder)
        outZipFile = os.path.join(export_zip_folder, self.component_id.engineering_code)
        checkCreateFolder(outZipFile)

        def exportSingle(docBws, filestorePath, outZipFile, withPdf=False, onlyPdf=False):
            if withPdf:
                srv = report.interface.report_int._reports['report.' + 'plm.document.pdf']
                datas, fileExtention = srv.create(self.env.cr, self.env.uid, [docBws.id], False, context=self.env.context)
                outFilePath = os.path.join(outZipFile, docBws.name + '.' + fileExtention)
                fileObj = file(outFilePath, 'wb')
                fileObj.write(datas)
            if not onlyPdf:
                fileName = os.path.join(filestorePath, self.env.cr.dbname, docBws.store_fname)
                if os.path.exists(fileName):
                    outFilePath = os.path.join(outZipFile, docBws.datas_fname)
                    shutil.copyfile(fileName, outFilePath)

        for viewObj in self.export_rel:
            docBws = viewObj.document_id
            if self.export_type in ('2d', '3d', '3d2d'):
                exportSingle(docBws, tmpSubFolder, outZipFile, False, False)
            elif self.export_type in ('2dpdf', '3dpdf', 'all'):
                exportSingle(docBws, tmpSubFolder, outZipFile, True, False)
            elif self.export_type in ('pdf'):
                exportSingle(docBws, tmpSubFolder, outZipFile, True, True)

        # Make archive, upload it and clean
        outZipFile2 = shutil.make_archive(outZipFile, 'zip', tmpSubSubFolder)
        with open(outZipFile2, 'rb') as f:
            fileContent = f.read()
            if fileContent:
                self.datas = base64.encodestring(fileContent)
        try:
            shutil.rmtree(tmpSubSubFolder)
            shutil.rmtree(fileContent)
        except Exception, ex:
            logging.error("Enable to delete file from export function %r %r" % (tmpSubSubFolder, unicode(ex)))
        fileName = os.path.basename(outZipFile2)
        self.datas_fname = fileName
        self.name = fileName
        return {'name': _('Pack and Go'),
                'view_type': 'form',
                "view_mode": 'form',
                'res_model': 'pack.and_go',
                'target': 'new',
                'res_id': self.ids[0],
                'type': 'ir.actions.act_window',
                'domain': "[]"}

    def getFileExtension(self, docBrws):
        fileExtension = ''
        datas_fname = docBrws.datas_fname
        if datas_fname:
            fileExtension = '.' + datas_fname.split('.')[-1]
        return fileExtension

    @api.multi
    def forceTypes3d(self):
        if not self.force_types_3d:
            raise UserError(_('You have to select a force type before clicking.'))
        forceType = self.force_types_3d.name
        for line in self.export_3d:
            typesObj = self.env['pack_and_go_types']
            res = typesObj.search([('name', '=', forceType)])
            if res:
                line.available_types = res.ids[0]
        return self.returnWizard()

    @api.multi
    def forceTypes2d(self):
        if not self.force_types_2d:
            raise UserError(_('You have to select a force type before clicking.'))
        forceType = self.force_types_2d.name
        for line in self.export_2d:
            typesObj = self.env['pack_and_go_types']
            res = typesObj.search([('name', '=', forceType)])
            if res:
                line.available_types = res.ids[0]
        return self.returnWizard()

PackAndGo()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
