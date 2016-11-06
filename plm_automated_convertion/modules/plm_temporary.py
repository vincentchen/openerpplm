##############################################################################
#
#    OmniaSolutions, Your own solutions
#    Copyright (C) 25/mag/2016 OmniaSolutions (<http://www.omniasolutions.eu>). All Rights Reserved
#    info@omniasolutions.eu
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
Created on 25/mag/2016

@author: mboscolo
'''

import logging
from openerp import models, fields, api, SUPERUSER_ID, _, osv
from openerp import tools
from openerp.exceptions import UserError
import base64
import os
import shutil
import requests
_logger = logging.getLogger(__name__)


def getCadAndConvertionAvailabe(fromExtention):
    availabeFormat = {'.e2': ('thinkdesign', ['.dxf', '.dwg']),
                      '.e3': ('thinkdesign', ['.iges', '.step']),
                      }
    return availabeFormat.get(str(fromExtention).lower(), ('', []))


class plm_temporary_batch_converter(osv.osv.osv_memory):
    _name = 'plm.convert'

    @api.model
    def getFileConverted(self,
                         document,
                         targetIntegration,
                         targetExtention,
                         newFileName=False):
        serverName = self.env['ir.config_parameter'].get_param('plm_convetion_server')
        if not serverName:
            raise Exception("Configure plm_convetion_server to use this functionality")
        url = 'http://%s/odooplm/api/v1.0/saveas' % serverName
        params = {}
        params['targetExtention'] = targetExtention
        params['integrationName'] = targetIntegration
        files = {'file': (document.datas_fname,
                          file(os.path.join(self.env['plm.document']._get_filestore(),
                                            document.store_fname),
                               'rb'))}
        response = requests.post(url,
                                 params=params,
                                 files=files)
        if response.status_code != 200:
            raise UserError("Convertion of cad server faild, check the cad server log")
        if newFileName:
            newFileName = document.datas_fname + targetExtention
        newTarget = os.path.join(os.environ['TEMP'], newFileName)
        with open(newTarget, 'wb') as f:
            f.write(response.content)
        return newTarget

    @api.model
    def calculate_available_extention(self):
        """
        calculate the conversion extension
        """
        datas_fname = self.env.context.get('datas_fname', False)
        if datas_fname:
            _, file_extension = os.path.splitext(datas_fname)
            _, avilableFormat = getCadAndConvertionAvailabe(file_extension)
            return [(a, a) for a in avilableFormat]
        return []

    document_id = fields.Many2one('plm.document',
                                  'Related Document')
    targetFormat = fields.Selection(selection='calculate_available_extention',
                                    string='Covertion Format',
                                    required=True)
    downloadDatas = fields.Binary('Download',
                                  attachment=True)
    datas_fname = fields.Char("New File name")

    @api.multi
    def convert(self):
        """
        """
        out = []
        for brwWizard in self:
            _, fileExtension = os.path.splitext(self.document_id.datas_fname)
            cadName, _ = getCadAndConvertionAvailabe(fileExtension)
            newFileName = ''
            for component in brwWizard.document_id.linkedcomponents:
                newFileName = component.engineering_code + brwWizard.targetFormat
            if newFileName == '':
                newFileName = self.document_id.datas_fname + '.' + brwWizard.targetFormat
            newFilePath = self.getFileConverted(brwWizard.document_id,
                                                cadName,
                                                brwWizard.targetFormat,
                                                newFileName)
            out.append(newFilePath)
        return out

    def action_create_coversion(self, cr, uid, ids, context={}):
        """
        convert the file to the give format
        """
        convertionFolder = self.pool.get('ir.config_parameter').get_param(cr,
                                                                          uid,
                                                                          'plm_convertion_folder')
        converted = self.convert(cr, uid, ids, context)
        for newFilePath in converted:
            try:
                shutil.move(newFilePath, convertionFolder)
            except Exception:
                newFileName = os.path.join(convertionFolder, os.path.basename(newFilePath))
                os.remove(newFileName)
                shutil.move(newFilePath, convertionFolder)
        UserError(_("File Converted check the shared folder"))

    def action_create_convert_download(self, cr, uid, ids, context={}):
        """
        Convert file in the given format and return it to the web page
        """
        for convertedFile in self.convert(cr, uid, ids, context):
            with open(convertedFile, 'rb') as f:
                fileContent = f.read()
                if fileContent:
                    self.write(cr, uid, ids, {'downloadDatas': base64.encodestring(fileContent),
                                              'datas_fname': os.path.basename(convertedFile)})
                    break
            break
        return {'name': _('File Converted'),
                'view_type': 'form',
                "view_mode": 'form',
                'res_model': self._name,
                'target': 'new',
                'res_id': ids[0],
                'type': 'ir.actions.act_window',
                'domain': "[]"}
plm_temporary_batch_converter()
