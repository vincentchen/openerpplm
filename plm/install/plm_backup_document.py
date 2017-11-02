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
Created on 11 Aug 2016

@author: Daniel Smerghetto
'''
from openerp.osv import osv, fields
from openerp import SUPERUSER_ID
from openerp.tools.translate import _
import logging
import os
import time
import stat


class plm_backupdoc(osv.osv):
    '''
        Only administrator is allowed to remove elements by this table
    '''
    _name = 'plm.backupdoc'
    _columns = {'userid': fields.many2one('res.users', 'Related User'),
                'createdate': fields.datetime('Date Created', readonly=True),
                'existingfile': fields.char('Physical Document Location', size=1024),
                'documentid': fields.many2one('plm.document', 'Related Document'),
                'revisionid': fields.related('documentid', 'revisionid', type="integer", relation="plm.document", string="Revision", store=True),
                'state': fields.related('documentid', 'state', type="char", relation="plm.document", string="Status", store=True),
                'document_name': fields.related('documentid', 'name', type="char", relation="plm.document", string="Stored Name", store=True),
                'printout': fields.binary('Printout Content'),
                'preview': fields.binary('Preview Content'),
                }
    _defaults = {
        'createdate': lambda self, cr, uid, ctx: time.strftime("%Y-%m-%d %H:%M:%S")
    }

    def unlink(self, cr, uid, ids, context=None):
        committed = False
        if context is not None and context != {}:
            if uid != SUPERUSER_ID:
                logging.warning("unlink : Unable to remove the required documents. You aren't authorized in this context.")
                raise osv.except_osv(_('Backup Error'), _("Unable to remove the required document.\n You aren't authorized in this context."))
                return False
        documentType = self.pool.get('plm.document')
        checkObjs = self.browse(cr, uid, ids, context=context)
        for checkObj in checkObjs:
            if not int(checkObj.documentid):
                return super(plm_backupdoc, self).unlink(cr, uid, ids, context=context)
            currentname = checkObj.documentid.store_fname
            if checkObj.existingfile != currentname:
                fullname = os.path.join(documentType._get_filestore(cr), checkObj.existingfile)
                if os.path.exists(fullname):
                    if os.path.exists(fullname):
                        os.chmod(fullname, stat.S_IWRITE)
                        os.unlink(fullname)
                        committed = True
                else:
                    logging.warning("unlink : Unable to remove the document (" + str(checkObj.documentid.name) + "-" + str(checkObj.documentid.revisionid) + ") from backup set. You can't change writable flag.")
                    raise osv.except_osv(_('Check-In Error'), _("Unable to remove the document (" + str(checkObj.documentid.name) + "-" + str(checkObj.documentid.revisionid) + ") from backup set.\n It isn't a backup file, it's original current one."))
        if committed:
            return super(plm_backupdoc, self).unlink(cr, uid, ids, context=context)
        else:
            return False

plm_backupdoc()


class BackupDocWizard(osv.osv_memory):
    '''
        This class is called from an action in xml located in plm.backupdoc.
        Pay attention! You can restore also confirmed, released and obsoleted documents!!!
        If you have a document AAA in PWS and you restore AAA from previous change client won't download it.
        You have to delete it from PWS and open again with the integration
    '''

    _name = 'plm.backupdoc_wizard'

    def action_restore_document(self, cr, uid, ids, context=None):
        '''
            Restore document from backup data
        '''

        documentId = False
        backupDocIds = context.get('active_ids', [])
        backupDocObj = self.pool.get('plm.backupdoc')
        plmDocObj = self.pool.get('plm.document')
        if len(backupDocIds) > 1:
            raise osv.except_osv(_('Restore Document Error'), _("You can restore only a document at a time."))
        for backupDocBrws in backupDocObj.browse(cr, uid, backupDocIds):
            relDocBrws = backupDocBrws.documentid
            values = {'printout': backupDocBrws.printout,
                      'store_fname': backupDocBrws.existingfile,
                      'preview': backupDocBrws.preview,
                      }
            if relDocBrws:
                documentId = relDocBrws.id
                writeRes = plmDocObj.write(cr, SUPERUSER_ID, relDocBrws.id, values)
                if writeRes:
                    logging.info('[action_restore_document] Updated document %r' % (documentId))
                else:
                    logging.warning('[action_restore_document] Updated document failed for %r' % (documentId))
            else:
                # Note that if I don't have a document I can't relate it to it's component
                # User have to do it hand made
                values.update({'state': 'draft',
                               'revisionid': backupDocBrws.revisionid,
                               'name': backupDocBrws.document_name,
                               }
                              )
                documentId = plmDocObj.create(cr, SUPERUSER_ID, values)
                if documentId:
                    logging.info('[action_restore_document] Created document %r' % (documentId))
                else:
                    logging.warning('[action_restore_document] Create document failed for %r' % (documentId))
        if documentId:
            return {'name': _('Document'),
                    'view_type': 'form',
                    "view_mode": 'form, tree',
                    'res_model': 'plm.document',
                    'res_id': documentId,
                    'type': 'ir.actions.act_window',
                    'domain': "[]"}
        return True

BackupDocWizard()
