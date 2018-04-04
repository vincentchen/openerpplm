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
import random
import string
import base64
import os
import json
import time
from datetime import datetime
from openerp.osv.orm import except_orm
import openerp.tools as tools
from openerp.exceptions import UserError
from openerp.osv import fields as oldFields
from openerp import models, fields, api, SUPERUSER_ID, _, osv
import logging
_logger = logging.getLogger(__name__)


# To be adequated to plm.component class states
USED_STATES = [('draft',_('Draft')),('confirmed',_('Confirmed')),('released',_('Released')),('undermodify',_('UnderModify')),('obsoleted',_('Obsoleted'))]
USEDIC_STATES = dict(USED_STATES)
#STATEFORRELEASE=['confirmed']
#STATESRELEASABLE=['confirmed','released','undermodify','UnderModify']

def random_name():
    random.seed()
    d = [random.choice(string.ascii_letters) for x in xrange(20) ]
    return ("".join(d))

def create_directory(path):
    dir_name = random_name()
    path = os.path.join(path, dir_name)
    os.makedirs(path)
    return dir_name

class plm_document(models.Model):
    _name = 'plm.document'
    _table = 'plm_document'
    _inherit = 'ir.attachment'

    def create(self, cr, uid, vals, context={}):
        return super(plm_document, self).create(cr, uid, vals, context)

    def get_checkout_user(self, cr, uid, oid, context={}):
        checkType = self.pool.get('plm.checkout')
        lastDoc = self._getlastrev(cr, uid, [oid], context)
        if lastDoc:
            for docID in checkType.search(cr, uid, [('documentid', '=', lastDoc[0])]):
                objectCheck = checkType.browse(cr, uid, docID)
                return objectCheck.userid
        False

    def _is_checkedout_for_me(self, cr, uid, oid, context=None):
        """
            Get if given document (or its latest revision) is checked-out for the requesting user
        """
        userBrws = self.get_checkout_user(cr, uid, oid, context=None)
        if userBrws:
            if userBrws.id == uid:
                return True
        return False

    def _getlastrev(self, cr, uid, ids, context=None):
        result = []
        for objDoc in self.browse(cr, uid, ids, context=context):
            docIds = self.search(cr, uid, [('name', '=', objDoc.name)], order='revisionid', context=context)
            docIds.sort()   # Ids are not surely ordered, but revision are always in creation order.
            if docIds:
                result.append(docIds[len(docIds) - 1])
            else:
                logging.warning('[_getlastrev] No documents are found for object with name: "%s"' % (objDoc.name))
        return list(set(result))

    def GetLastNamesFromID(self, cr, uid, ids=[], context={}):
        """
            get the last rev
        """
        newIds = self._getlastrev(cr, uid, ids=ids, context=context)
        return self.read(cr, uid, newIds, ['datas_fname'], context=context)

    def _data_get_files(self, cr, uid, ids, listedFiles=([], []), forceFlag=False, context=None):
        """
            Get Files to return to Client
        """
        result = []
        logging.info("Start collecting file For download")
        totalByte = 0
        datefiles, listfiles = listedFiles
        for objDoc in self.browse(cr, uid, ids, context=context):
            if objDoc.file_size:
                totalByte = totalByte + objDoc.file_size
            if objDoc.type == 'binary':
                timeDoc = self.getLastTime(cr, uid, objDoc.id)
                timeSaved = time.mktime(timeDoc.timetuple())
                try:
                    isCheckedOutToMe = self._is_checkedout_for_me(cr, uid, objDoc.id, context)
                    if not(objDoc.datas_fname in listfiles):
                        if (not objDoc.store_fname) and (objDoc.db_datas):
                            value = objDoc.db_datas
                        else:
                            value = file(os.path.join(self._get_filestore(cr), objDoc.store_fname), 'rb').read()
                        result.append((objDoc.id, objDoc.datas_fname, base64.encodestring(value), isCheckedOutToMe, timeDoc))
                    else:
                        if forceFlag:
                            isNewer = True
                        else:
                            timefile = time.mktime(datetime.strptime(str(datefiles[listfiles.index(objDoc.datas_fname)]), '%Y-%m-%d %H:%M:%S').timetuple())
                            isNewer = (timeSaved - timefile) > 5
                        if (isNewer and not(isCheckedOutToMe)):
                            if (not objDoc.store_fname) and (objDoc.db_datas):
                                value = objDoc.db_datas
                            else:
                                value = file(os.path.join(self._get_filestore(cr), objDoc.store_fname), 'rb').read()
                            result.append((objDoc.id, objDoc.datas_fname, base64.encodestring(value), isCheckedOutToMe, timeDoc))
                        else:
                            result.append((objDoc.id, objDoc.datas_fname, False, isCheckedOutToMe, timeDoc))
                except Exception, ex:
                    logging.error("_data_get_files : Unable to access to document (" + str(objDoc.name) + "). Error :" + str(ex))
                    result.append((objDoc.id, objDoc.datas_fname, False, True, self.getServerTime(cr, uid, ids)))
        logging.info("Start sending %r object to the client in byte: %r" % (len(result), totalByte))
        return result

    def _data_get(self, cr, uid, ids, name, arg, context):
        result = {}
        for objDoc in self.browse(cr, uid, ids, context=context):
            if objDoc.type == 'binary':
                value = ''
                if not objDoc.store_fname:
                    value = objDoc.db_datas
                else:
                    filestore = os.path.join(self._get_filestore(cr), objDoc.store_fname)
                    if os.path.exists(filestore):
                        value = file(filestore, 'rb').read()
                    else:
                        msg = "Document %s-%s is not in %r" % (str(objDoc.name),
                                                               str(objDoc.revisionid),
                                                               filestore)

                        logging.error(msg)
                if value and len(value) > 0:
                    result[objDoc.id] = base64.encodestring(value)
                else:
                    result[objDoc.id] = ''
                    msg = "Document %s - %s cannot be accessed" % (str(objDoc.name),
                                                                   str(objDoc.revisionid))
                    logging.warning(msg)
        return result

    def _data_set(self, cr, uid, oid, name, value, args=None, context=None):
        oiDocument = self.browse(cr, uid, oid, context)
        if oiDocument.type == 'binary':
            if not value:
                filename = oiDocument.store_fname
                try:
                    os.unlink(os.path.join(self._get_filestore(cr), filename))
                except:
                    pass
                cr.execute('update plm_document set store_fname=NULL WHERE id=%s', (oid,))
                return True
            try:
                printout = False
                preview = False
                if oiDocument.printout:
                    printout = oiDocument.printout
                if oiDocument.preview:
                    preview = oiDocument.preview
                db_datas = b''                    # Clean storage field.
                fname, filesize = self._manageFile(cr, uid, oid, binvalue=value, context=context)
                cr.execute('update plm_document set store_fname=%s,file_size=%s,db_datas=%s where id=%s', (fname, filesize, db_datas, oid))
                self.pool.get('plm.backupdoc').create(cr, uid, {'documentid': oid,
                                                                'userid': uid,
                                                                'existingfile': fname,
                                                                'printout': printout,
                                                                'preview': preview
                                                                }, context=context)

                return True
            except Exception, ex:
                raise UserError(_('Error in _data_set %r' % ex))
        else:
            return True

    def _explodedocs(self, cr, uid, oid, kinds, listed_documents=[], recursion=True):
        result = []
        documentRelation = self.pool.get('plm.document.relation')

        def getAllDocumentChildId(fromID, kinds):
            docRelIds = documentRelation.search(cr, uid, [('parent_id', '=', fromID), ('link_kind', 'in', kinds)])
            children = documentRelation.browse(cr, uid, docRelIds)
            for child in children:
                idToAdd = child.child_id.id
                if idToAdd not in result:
                    result.append(idToAdd)
                    if recursion:
                        getAllDocumentChildId(idToAdd, kinds)
        getAllDocumentChildId(oid, kinds)
        return result

    def _relateddocs(self, cr, uid, oid, kinds, listed_documents=[], recursion=True):
        result=[]
        if (oid in listed_documents):
            return result
        documentRelation=self.pool.get('plm.document.relation')
        docRelIds=documentRelation.search(cr,uid,[('child_id', '=',oid),('link_kind', 'in',kinds)])
        if len(docRelIds)==0:
            return result
        children=documentRelation.browse(cr,uid,docRelIds)
        for child in children:
            if recursion:
                listed_documents.append(oid)
                result.extend(self._relateddocs(cr, uid, child.parent_id.id, kinds, listed_documents, recursion))
            if child.parent_id:
                result.append(child.parent_id.id)
        return list(set(result))

    def _relatedbydocs(self, cr, uid, oid, kinds, listed_documents=[], recursion=True):
        result = []
        if (oid in listed_documents):
            return result
        documentRelation = self.pool.get('plm.document.relation')
        docRelIds = documentRelation.search(cr,
                                            uid,
                                            [('parent_id', '=',oid),
                                             ('link_kind', 'in',kinds)])
        if len(docRelIds) == 0:
            return result
        children = documentRelation.browse(cr, uid, docRelIds)
        for child in children:
            if recursion:
                listed_documents.append(oid)
                result.extend(self._relatedbydocs(cr, uid, child.child_id.id, kinds, listed_documents, recursion))
            if child.child_id.id:
                result.append(child.child_id.id)
        return list(set(result))

    def _data_check_files(self, cr, uid, ids, listedFiles=(), forceFlag=False, context=None):
        maxTargetFileSize = self.pool.get('ir.config_parameter').get_param(cr, uid, 'max_download_file_size', default=5000000000)
        maxTargetFileSize = int(maxTargetFileSize)
        result = []
        datefiles = []
        listfiles = []
        if len(listedFiles) > 0:
            datefiles, listfiles = listedFiles
        for objDoc in self.browse(cr, uid, list(set(ids)), context=context):
            logging.info("work on on id %r" % objDoc.id)
            if objDoc.type == 'binary':
                checkOutUser = ''
                isCheckedOutToMe = False
                timeDoc = self.getLastTime(cr, uid, objDoc.id)
                timeSaved = time.mktime(timeDoc.timetuple())
                checkoutUserBrws = self.get_checkout_user(cr, uid, objDoc.id, context=None)
                if checkoutUserBrws:
                    checkOutUser = checkoutUserBrws.name
                    if checkoutUserBrws.id == uid:
                        isCheckedOutToMe = True
                datas_fname = objDoc.datas_fname
                if (datas_fname in listfiles):
                    if forceFlag:
                        isNewer = True
                    else:
                        try:
                            listFileIndex = listfiles.index(datas_fname)
                            timefile = time.mktime(datetime.strptime(str(datefiles[listFileIndex]), '%Y-%m-%d %H:%M:%S').timetuple())
                            isNewer = (timeSaved - timefile) > 5
                        except:
                            logging.warning("Unable to calculate the delta time for %r" % datas_fname)
                            isNewer = True
                    collectable = isNewer and not(isCheckedOutToMe)
                else:
                    collectable = True
                filestorePath = self._get_filestore(cr)
                completePath = os.path.join(filestorePath, objDoc.store_fname)
                file_size = 1
                if os.path.exists(completePath):
                    file_size = os.path.getsize(completePath)
                if file_size <= 1:
                    logging.error('Document with "id": %s and "name": %s may contains no data!!' % (objDoc.id, datas_fname))
                outId = objDoc.id
                if file_size > maxTargetFileSize:
                    # This case is used to split big files and download them, see the client for more info
                    outId = (objDoc.id, tuple(range(0, len(range(0, file_size, maxTargetFileSize)))))
                result.append((outId,
                               objDoc.datas_fname,
                               file_size,
                               collectable,
                               isCheckedOutToMe,
                               checkOutUser))
        logging.info("Going out to _data_check_files")
        return list(set(result))

    def getPartOfFile(self, cr, uid, result, context={}):
        docId, tokenIndex = result
        maxTargetFileSize = self.pool.get('ir.config_parameter').get_param(cr, uid, 'max_download_file_size', default=500000000)
        maxTargetFileSize = int(maxTargetFileSize)
        objDoc = self.browse(cr, uid, docId, context)
        if objDoc:
            completeData = objDoc.datas
            splittedDatas = [completeData[i:i + maxTargetFileSize] for i in range(0, len(completeData), maxTargetFileSize)]
            return base64.encodestring(splittedDatas[tokenIndex]), objDoc.datas_fname

    def copy(self,cr,uid,oid,defaults={},context=None):
        """
            Overwrite the default copy method
        """
        #get All document relation 
        documentRelation=self.pool.get('plm.document.relation')
        docRelIds=documentRelation.search(cr,uid,[('parent_id', '=',oid)],context=context)
        if len(docRelIds)==0:
            docRelIds=False 
        previous_name=self.browse(cr,uid,oid,context=context).name
        if not 'name' in defaults:
            new_name='Copy of %s'%previous_name
            l=self.search(cr,uid,[('name','=',new_name)],order='revisionid',context=context)
            if len(l)>0:
                new_name='%s (%s)'%(new_name,len(l)+1)
            defaults['name']=new_name
        #manage copy of the file
        fname,filesize=self._manageFile(cr,uid,oid,context=context)
        #assign default value
        defaults['store_fname']=fname
        defaults['file_size']=filesize
        defaults['state']='draft'
        defaults['writable']=True
        newID=super(plm_document,self).copy(cr,uid,oid,defaults,context=context)
        if (newID):
            self.wf_message_post(cr, uid, [newID], body=_('Copied starting from : %s.' %previous_name))
        if docRelIds:
            # create all the document relation
            brwEnts=documentRelation.browse(cr,uid,docRelIds,context=context)
            for brwEnt in brwEnts:
                documentRelation.create(cr,uid, {
                                          'parent_id':newID,
                                          'child_id':brwEnt.child_id.id,
                                          'configuration':brwEnt.configuration,
                                          'link_kind':brwEnt.link_kind,
                                         }, context=context)
        return newID 

    def _manageFile(self, cr, uid, oid, binvalue=None, context=None):
        """
            use given 'binvalue' to save it on physical repository and to read size (in bytes).
        """
        path = self._get_filestore(cr)
        if not os.path.isdir(path):
            try:
                os.makedirs(path)
            except:
                raise UserError(_("Permission denied or directory %s cannot be created." % (str(path))))
        storeDirectory = None
        # This can be improved
        for dirs in os.listdir(path):
            if os.path.isdir(os.path.join(path, dirs)) and len(os.listdir(os.path.join(path, dirs))) < 4000:
                storeDirectory = dirs
                break
        if binvalue is None:
            fileStream = self._data_get(cr, uid, [oid], name=None, arg=None, context=context)
            binvalue = fileStream[fileStream.keys()[0]]
        storeDirectory = storeDirectory or create_directory(path)
        filename = random_name()
        fname = os.path.join(path, storeDirectory, filename)
        with file(fname, 'wb') as fobj:
            value = base64.decodestring(binvalue)
            fobj.write(value)
            return (os.path.join(storeDirectory, filename), len(value))

    @api.model
    def _iswritable(self, oid):
        if not oid.type == 'binary':
            logging.warning("_iswritable : Part (" + str(oid.name) + "-" + str(oid.revisionid) + ") not writable as hyperlink.")
            return False
        if oid.state not in ('draft'):
            logging.warning("_iswritable : Part (" + str(oid.name) + "-" + str(oid.revisionid) + ") in status ; " + str(oid.state) + ".")
            return False
        if not oid.name:
            logging.warning("_iswritable : Part (" + str(oid.name) + "-" + str(oid.revisionid) + ") without Engineering P/N.")
            return False
        return True

    def newVersion(self, cr, uid, ids, context=None):
        """
            create a new version of the document (to WorkFlow calling)
        """
        if self.NewRevision(cr, uid, ids, context=context) is not None:
            return True
        return False

    def NewRevision(self, cr, uid, ids, newBomDocumentRevision=True, context=None):
        """
            create a new revision of the document
        """
        # TODO: Migrate document revision functionality from plm 10
        if isinstance(ids, (list, tuple)):  # This is to fix new style call
            context = newBomDocumentRevision
            ids, newBomDocumentRevision = ids
        newID = None
        for tmpObject in self.browse(cr, uid, ids, context=context):
            latestIDs = self.GetLatestIds(cr, uid, [(tmpObject.name, tmpObject.revisionid, False)], context=context)
            for oldObject in self.browse(cr, uid, latestIDs, context=context):
                self.write(cr, uid, [oldObject.id], {'state': 'undermodify'}, context=context, check=False)
                defaults                = {}
                defaults['name']        = oldObject.name
                defaults['revisionid']  = int(oldObject.revisionid) + 1
                defaults['writable']    = True
                defaults['state']       = 'draft'
                newID = super(plm_document, self).copy(cr, uid, oldObject.id, defaults, context=context)
                self.wf_message_post(cr, uid, [oldObject.id], body=_('Created : New Revision.'))
                break
            break
        return (newID, defaults['revisionid'])

    def Clone(self, cr, uid, oid, defaults={}, context=None):
        """
            create a new copy of the document
        """
        defaults    = {}
        exitValues  = {}
        newID       = self.copy(cr, uid, oid, defaults, context)
        if newID is not None:
            newEnt = self.browse(cr, uid, newID, context=context)
            exitValues['_id']           = newID
            exitValues['name']          = newEnt.name
            exitValues['revisionid']    = newEnt.revisionid
        return exitValues

    def CheckSaveUpdate(self, cr, uid, documents, default=None, context=None):
        """
            Save or Update Documents
        """
        retValues = []
        for document in documents:
            hasToBeSaved = False
            if not ('name' in document) or (not 'revisionid' in document):
                document['documentID']  = False
                document['hasSaved']    = hasToBeSaved
                continue
            existingID = self.search(cr, uid, [
                                           ('name', '=', document['name']),
                                           ('revisionid', '=', document['revisionid'])], order='revisionid')
            if not existingID:
                hasToBeSaved = True
            else:
                existingID  = existingID[0]
                objDocument = self.browse(cr, uid, existingID, context=context)
                if objDocument.writable:
                    if objDocument.file_size > 0 and objDocument.datas_fname:
                        if self.getLastTime(cr, uid, existingID) < datetime.strptime(str(document['lastupdate']), '%Y-%m-%d %H:%M:%S'):
                            hasToBeSaved = True
                    else:
                        hasToBeSaved = True
            document['documentID'] = existingID
            document['hasSaved'] = hasToBeSaved
            retValues.append(document)
        return retValues

    def SaveOrUpdate(self, cr, uid, documents, default=None, context=None):
        """
            Save or Update Documents
        """
        retValues = []
        for document in documents:
            hasSaved = False
            hasUpdated = False
            if not ('name' in document) or (not 'revisionid' in document):
                document['documentID'] = False
                document['hasSaved'] = hasSaved
                document['hasUpdated'] = hasUpdated
                continue
            existingID = self.search(cr, uid, [('name', '=', document['name']), ('revisionid', '=', document['revisionid'])], order='revisionid')
            if not existingID:
                existingID = self.create(cr, uid, document)
                hasSaved = True
            else:
                existingID = existingID[0]
                objDocument = self.browse(cr, uid, existingID, context=context)
                if self.getLastTime(cr, uid, existingID) < datetime.strptime(str(document['lastupdate']), '%Y-%m-%d %H:%M:%S'):
                    if self._iswritable(cr, uid, objDocument):
                        del(document['lastupdate'])
                        if not self.write(cr, uid, [existingID], document, context=context, check=True):
                            raise UserError(_("Document %s  -  %s cannot be updated" % (str(document['name']), str(document['revisionid']))))
                        hasSaved = True
            document['documentID'] = existingID
            document['hasSaved'] = hasSaved
            document['hasUpdated'] = hasUpdated
            retValues.append(document)
        return retValues

    def RegMessage(self, cr, uid, request, default=None, context=None):
        """
            Registers a message for requested document
        """
        oid, message = request
        self.wf_message_post(cr, uid, [oid], body=_(message))
        return False

    def UpdateDocuments(self, cr, uid, documents, default=None, context=None):
        """
            Save or Update Documents
        """
        ret = True
        for document in documents:
            oid = document['documentID']
            del(document['documentID'])
            ret = ret and self.write(cr, uid, [oid], document, context=context, check=True)
        return ret

    def CleanUp(self, cr, uid, ids, default=None, context=None):
        """
            Remove faked documents
        """
        cr.execute("delete from plm_document where store_fname=NULL and type='binary'")
        return True

    def QueryLast(self, cr, uid, request=([], []), default=None, context=None):
        """
            Query to return values based on columns selected.
        """
        expData = []
        queryFilter, columns = request
        if len(columns) < 1:
            return expData
        if 'revisionid' in queryFilter:
            del queryFilter['revisionid']
        allIDs = self.search(cr, uid, queryFilter, order='revisionid', context=context)
        if len(allIDs) > 0:
            allIDs.sort()
            tmpData = self.export_data(cr, uid, allIDs, columns)
            if 'datas' in tmpData:
                expData = tmpData['datas']
        return expData

    def ischecked_in(self, cr, uid, ids, context=None):
        """
            Check if a document is checked-in
        """
        documents = self.browse(cr, uid, ids, context=context)
        checkoutType = self.pool.get('plm.checkout')

        for document in documents:
            if checkoutType.search(cr, uid, [('documentid', '=', document.id)], context=context):
                logging.warning(_("The document %s - %s has not checked-in" % (str(document.name), str(document.revisionid))))
                return False
        return True

    def wf_message_post(self, cr, uid, ids, body='', context=None):
        """
            Writing messages to follower, on multiple objects
        """
        if not (body == ''):
            for idd in ids:
                self.message_post(cr, uid, [idd], body=_(body))

    def action_draft(self, cr, uid, ids, *args):
        """
            release the object
        """
        defaults = {}
        defaults['writable'] = True
        defaults['state'] = 'draft'
        objId = self.write(cr, uid, ids, defaults, check=False)
        if (objId):
            self.wf_message_post(cr, uid, ids, body=_('Status moved to: %s.' % (USEDIC_STATES[defaults['state']])))
        return objId

    def action_confirm(self, cr, uid, ids, context=None):
        """
            action to be executed for Draft state
        """
        defaults = {}
        defaults['writable'] = False
        defaults['state'] = 'confirmed'
        if self.ischecked_in(cr, uid, ids, context):
            objId = self.write(cr, uid, ids, defaults, context=context, check=False)
            if (objId):
                self.wf_message_post(cr, uid, ids, body=_('Status moved to: %s.' % (USEDIC_STATES[defaults['state']])))
            return objId
        return False

    def action_release(self, cr, uid, ids, *args):
        """
            release the object
        """
        defaults = {}
        for oldObject in self.browse(cr, uid, ids, context=None):
            last_id = self._getbyrevision(cr, uid, oldObject.name, oldObject.revisionid - 1)
            if last_id is not None:
                defaults['writable'] = False
                defaults['state'] = 'obsoleted'
                self.write(cr, uid, [last_id], defaults, check=False)
                self.wf_message_post(cr, uid, [last_id], body=_('Status moved to: %s.' % (USEDIC_STATES[defaults['state']])))
        defaults['writable'] = False
        defaults['state'] = 'released'
        if self.ischecked_in(cr, uid, ids):
            objId = self.write(cr, uid, ids, defaults, check=False)
            if (objId):
                self.wf_message_post(cr, uid, ids, body=_('Status moved to: %s.' % (USEDIC_STATES[defaults['state']])))
            return objId
        return False

    def action_obsolete(self, cr, uid, ids, context=None):
        """
            obsolete the object
        """
        defaults = {}
        defaults['writable'] = False
        defaults['state'] = 'obsoleted'
        if self.ischecked_in(cr, uid, ids, context):
            objId = self.write(cr, uid, ids, defaults, context=context, check=False)
            if (objId):
                self.wf_message_post(cr, uid, ids, body=_('Status moved to: %s.' % (USEDIC_STATES[defaults['state']])))
            return objId
        return False

    def action_reactivate(self, cr, uid, ids, context=None):
        """
            reactivate the object
        """
        defaults = {}
        defaults['engineering_writable'] = False
        defaults['state'] = 'released'
        if self.ischecked_in(cr, uid, ids, context):
            objId = self.write(cr, uid, ids, defaults, context=context, check=False)
            if (objId):
                self.wf_message_post(cr, uid, ids, body=_('Status moved to:%s.' % (USEDIC_STATES[defaults['state']])))
            return objId
        return False

    def blindwrite(self, cr, uid, ids, vals, context=None):
        """
            blind write for xml-rpc call for recovering porpouse
            DO NOT USE FOR COMMON USE !!!!
        """
        return self.write(cr, uid, ids, vals, context=context, check=False)

#   Overridden methods for this entity
    def _get_filestore(self, cr):
        dms_Root_Path = tools.config.get('document_path', os.path.join(tools.config['root_path'], 'filestore'))
        return os.path.join(dms_Root_Path, cr.dbname)

#     def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
#         # Grab ids, bypassing 'count'
#         ids = osv.osv.osv.search(self,cr, uid, args, offset=offset, limit=limit, order=order, context=context, count=False)
#         if not ids:
#             return 0 if count else []
#
#         # Filter out documents that are in directories that the user is not allowed to read.
#         # Must use pure SQL to avoid access rules exceptions (we want to remove the records,
#         # not fail), and the records have been filtered in parent's search() anyway.
#         cr.execute('SELECT id, parent_id from plm_document WHERE id in %s', (tuple(ids),))
#
#         # cont a dict of parent -> attach
#         parents = {}
#         for attach_id, attach_parent in cr.fetchall():
#             parents.setdefault(attach_parent, []).append(attach_id)
#         parent_ids = parents.keys()
#
#         # filter parents
#         visible_parent_ids = self.pool.get('document.directory').search(cr, uid, [('id', 'in', list(parent_ids))])
#
#         # null parents means allowed
#         ids = parents.get(None,[])
#         for parent_id in visible_parent_ids:
#             ids.extend(parents[parent_id])
#
#         return len(ids) if count else ids

    def write(self, cr, uid, ids, vals, context=None, check=True):
        checkState = ('confirmed', 'released', 'undermodify', 'obsoleted')
        if check:
            for customObject in self.browse(cr, uid, ids, context=context):
                if customObject.state in checkState:
                    raise UserError(_("The active state does not allow you to make save action"))
                    return False
        self.writeCheckDatas(cr, uid, ids, vals, context)
        return super(plm_document, self).write(cr, uid, ids, vals, context=context)
        
    @api.multi
    def writeCheckDatas(self, vals):
        if 'datas' in vals.keys() or 'datas_fname' in vals.keys():
            for docBrws in self:
                if not docBrws._is_checkedout_for_me(docBrws.id) and self.env.uid != SUPERUSER_ID:
                    raise UserError(_("You cannot edit a file not in check-out by you! User ID %s" % (self.env.uid)))

    def unlink(self, cr, uid, ids, context=None):
        values = {'state': 'released', }
        checkState = ('undermodify', 'obsoleted')
        for checkObj in self.browse(cr, uid, ids, context=context):
            existingID = self.search(cr, uid, [('name', '=', checkObj.name), ('revisionid', '=', checkObj.revisionid - 1)])
            if len(existingID) > 0:
                oldObject = self.browse(cr, uid, existingID[0], context=context)
                if oldObject.state in checkState:
                    self.wf_message_post(cr, uid, [oldObject.id], body=_('Removed : Latest Revision.'))
                    if not self.write(cr, uid, [oldObject.id], values, context=context, check=False):
                        logging.warning("unlink : Unable to update state to old document (" + str(oldObject.name) + "-" + str(oldObject.revisionid) + ").")
                        return False
        return super(plm_document, self).unlink(cr, uid, ids, context=context)

#   Overridden methods for this entity

    def _check_duplication(self, cr, uid, vals, ids=None, op='create'):
        SUPERUSER_ID = 1
        name = vals.get('name', False)
        parent_id = vals.get('parent_id', False)
        ressource_parent_type_id = vals.get('ressource_parent_type_id', False)
        ressource_id = vals.get('ressource_id', 0)
        revisionid = vals.get('revisionid', 0)
        if op == 'write':
            for directory in self.browse(cr, SUPERUSER_ID, ids):
                if not name:
                    name = directory.name
                if not parent_id:
                    parent_id = directory.parent_id and directory.parent_id.id or False
                # TODO fix algo
                if not ressource_parent_type_id:
                    ressource_parent_type_id = directory.ressource_parent_type_id and directory.ressource_parent_type_id.id or False
                if not ressource_id:
                    ressource_id = directory.ressource_id and directory.ressource_id or 0
                res = self.search(cr, uid, [('id', '<>', directory.id), ('name', '=', name), ('parent_id', '=', parent_id), ('ressource_parent_type_id', '=', ressource_parent_type_id), ('ressource_id', '=', ressource_id), ('revisionid', '=', revisionid)])
                if len(res):
                    return False
        if op == 'create':
            res = self.search(cr, SUPERUSER_ID, [('name', '=', name), ('parent_id', '=', parent_id), ('ressource_parent_type_id', '=', ressource_parent_type_id), ('ressource_id', '=', ressource_id), ('revisionid', '=', revisionid)])
            if len(res):
                return False
        return True
#   Overridden methods for this entity

    @api.one
    def _get_checkout_state(self):
        chechRes = self.getCheckedOut(self.id, None)
        if chechRes:
            self.checkout_user = str(chechRes[2])
        else:
            self.checkout_user = ''

    @api.one
    def _is_checkout(self):
        chechRes = self.getCheckedOut(self.id, None)
        if chechRes:
            self.is_checkout = True
        else:
            self.is_checkout = False

    def getFileExtension(self, docBrws):
        fileExtension = ''
        datas_fname = docBrws.datas_fname
        if datas_fname:
            fileExtension = '.' + datas_fname.split('.')[-1]
        return fileExtension

    @api.multi
    def _compute_document_type(self):
        configParamObj = self.env['ir.config_parameter']
        str2DExtensions = configParamObj._get_param('file_exte_type_rel_2D')
        str3DExtensions = configParamObj._get_param('file_exte_type_rel_3D')
        for docBrws in self:
            try:
                fileExtension = docBrws.getFileExtension(docBrws)
                extensions2D = eval(str2DExtensions)
                extensions3D = eval(str3DExtensions)
                if fileExtension in extensions2D:
                    docBrws.document_type = '2d'
                elif fileExtension in extensions3D:
                    docBrws.document_type = '3d'
                else:
                    docBrws.document_type = 'other'
            except Exception, ex:
                logging.error('Unable to compute document type for document %r, error %r' % (docBrws.id, ex))

    usedforspare    =   fields.Boolean(_('Used for Spare'), help=_("Drawings marked here will be used printing Spare Part Manual report."))
    revisionid      =   fields.Integer(_('Revision Index'), required=True)
    writable        =   fields.Boolean(_('Writable'))
    #  datas           =   fields.Binary   (fnct_inv=_data_set,compute=_data_get,method=True,string=_('File Content'))
    printout        =   fields.Binary(_('Printout Content'), help=_("Print PDF content."))
    preview         =   fields.Binary(_('Preview Content'), help=_("Static preview."))
    state           =   fields.Selection(USED_STATES, _('Status'), help=_("The status of the product."), readonly="True", required=True)
    checkout_user   =   fields.Char(string=_("Checked-Out to"), compute=_get_checkout_state)
    is_checkout     =   fields.Boolean(_('Is Checked-Out'), compute=_is_checkout, store=False)
    
    document_type = fields.Selection([('2d', _('2D')),
                                      ('3d', _('3D')),
                                      ('other', _('Other')),
                                      ], 
                                     compute=_compute_document_type,
                                     string= _('Document Type'))

    _columns = {
                'datas': oldFields.function(_data_get, method=True, fnct_inv=_data_set, string=_('File Content'), type="binary"),
                #'checkout_user':fields.function(_get_checkout_state, type='char', string="Checked-Out to"),
                #'is_checkout':fields.function(_is_checkout, type='boolean', string="Is Checked-Out", store=False)
                }
    _defaults = {
                 'usedforspare': False,
                 'revisionid': lambda *a: 0,
                 'writable': lambda *a: True,
                 'state': lambda *a: 'draft',
    }

    _sql_constraints = [
        ('name_unique', 'unique (name, revisionid)', 'File name has to be unique!')  # qui abbiamo la sicurezza dell'univocita del nome file
    ]

    def CheckedIn(self, cr, uid, files, default=None, context=None):
        """
            Get checked status for requested files
        """
        retValues = []

        def getcheckedfiles(files):
            res = []
            for fileName in files:
                ids = self.search(cr, uid, [('datas_fname', '=', fileName)], order='revisionid')
                if len(ids) > 0:
                    ids.sort()
                    res.append([fileName, not (self._is_checkedout_for_me(cr, uid, ids[len(ids) - 1], context))])
            return res

        if len(files) > 0:  # no files to process
            retValues = getcheckedfiles(files)
        return retValues

    def GetUpdated(self, cr, uid, vals, context=None):
        """
            Get Last/Requested revision of given items (by name, revision, update time)
        """
        docData, attribNames = vals
        ids = self.GetLatestIds(cr, uid, docData, context)
        return self.read(cr, uid, list(set(ids)), attribNames)

    def GetLatestIds(self, cr, uid, vals, context=None, forceCADProperties=False):
        """
            Get Last/Requested revision of given items (by name, revision, update time)
        """
        ids = []

        def getCompIds(docName, docRev):
            if docRev is None or docRev is False:
                docIds = self.search(cr, uid, [('name', '=', docName)], order='revisionid', context=context)
                if len(docIds) > 0:
                    ids.append(docIds[-1])
            else:
                ids.extend(self.search(cr, uid, [('name', '=', docName), ('revisionid', '=', docRev)], context=context))

        for docName, docRev, docIdToOpen in vals:
            checkOutUser = self.get_checkout_user(cr, uid, docIdToOpen, context)
            if checkOutUser:
                isMyDocument = self.isCheckedOutByMe(cr, uid, docIdToOpen, context)
                if isMyDocument:
                    return []    # Document properties will be not updated
                else:
                    getCompIds(docName, docRev)
            else:
                getCompIds(docName, docRev)
        return list(set(ids))

    @api.multi
    def isCheckedOutByMe(self):
        checkoutBrwsList = self.env['plm.checkout'].search([('documentid', '=', self.id), ('userid', '=', self.env.uid)])
        for checkoutBrws in checkoutBrwsList:
            return checkoutBrws.id
        return None

    def CheckAllFiles(self, cr, uid, request, default=None, context=None):
        """
            Evaluate documents to return
        """
        forceFlag = False
        outIds = []
        oid, listedFiles, selection = request
        outIds.append(oid)
        if selection is False:
            selection = 1   # Case of selected
        if selection < 0:   # Case of force refresh PWS
            forceFlag = True
            selection = selection * (-1)
        # Get relations due to layout connected
        docArray = self._relateddocs(cr, uid, oid, ['LyTree'], [])
        logging.info("LyTree Len of docArray: %r" % len(docArray))
        # Get Hierarchical tree relations due to children
        modArray = self._explodedocs(cr, uid, oid, ['HiTree'], [])
        logging.info("HiTree Len of modArray: %r" % len(modArray))
        outIds = list(set(outIds + modArray + docArray))
        if selection == 2:  # Case of latest
            outIds = self._getlastrev(cr, uid, outIds, context)
        return self._data_check_files(cr, uid, outIds, listedFiles, forceFlag, context)

    @api.model
    def CheckIn(self, attrs):
        documentName = attrs.get('name', '')
        revisionId = attrs.get('revisionid', False)
        docBrwsList = self.search([('name', '=', documentName),
                                   ('revisionid', '=', revisionId)])
        for docBrws in docBrwsList:
            checkOutId = docBrws.isCheckedOutByMe()
            if not checkOutId:
                logging.info('Document %r is not in check out by user %r so cannot be checked-in' % (docBrws.id, self.env.user_id))
                return False
            if docBrws.file_size <= 0 or not docBrws.datas_fname:
                logging.warning('Document %r has not document content so cannot be checked-in' % (docBrws.id))
                return False
            self.env['plm.checkout'].browse(checkOutId).unlink()
            return docBrws.id
        return False
        
    def CheckInRecursive(self, cr, uid, request, default=None, context=None):
        """
            Evaluate documents to return
        """
        def getDocId(args):
            docName = args.get('name')
            docRev = args.get('revisionid')
            docIds = self.search(cr, uid, [('name', '=', docName), ('revisionid', '=', docRev)])
            if not docIds:
                logging.warning('Document with name "%s" and revision "%s" not found' % (docName, docRev))
                return False
            return docIds[0]

        oid, _listedFiles, selection = request
        oid = getDocId(oid)
        docBrws = self.browse(cr, uid, oid, context)
        checkRes = self.isCheckedOutByMe(cr, uid, oid, context)
        if not checkRes:
            logging.info('Document %r is not in check out by user %r so cannot be checked-in recursively' % (oid, uid))
            return False
        if docBrws.file_size <= 0 or not docBrws.datas_fname:
            logging.warning('Document %r has not document content so cannot be checked-in recirsively' % (oid))
            return False
        if selection is False:
            selection = 1
        if selection < 0:
            selection = selection * (-1)
        documentRelation = self.pool.get('plm.document.relation')
        docArray = []

        def recursionCompute(oid):
            if oid in docArray:
                return
            else:
                docArray.append(oid)
            docRelIds = documentRelation.search(cr, uid, ['|', ('parent_id', '=', oid), ('child_id', '=', oid)])
            for objRel in documentRelation.browse(cr, uid, docRelIds, context):
                if objRel.link_kind in ['LyTree', 'RfTree'] and objRel.child_id.id not in docArray:
                    docArray.append(objRel.child_id.id)
                else:
                    if objRel.parent_id.id == oid:
                        recursionCompute(objRel.child_id.id)

        recursionCompute(oid)
        if selection == 2:
            docArray = self._getlastrev(cr, uid, docArray, context)
        checkoutObj = self.pool.get('plm.checkout')
        for docId in docArray:
            checkoutId = checkoutObj.search(cr, uid, [('documentid', '=', docId), ('userid', '=', uid)], context)
            if checkoutId:
                checkoutObj.unlink(cr, uid, checkoutId)
        return self.read(cr, uid, docArray, ['datas_fname'], context)

    def GetSomeFiles(self, cr, uid, request, default=None, context=None):
        """
            Extract documents to be returned 
        """
        forceFlag=False
        ids, listedFiles, selection = request
        if selection == False:
            selection=1

        if selection<0:
            forceFlag=True
            selection=selection*(-1)

        if selection == 2:
            docArray=self._getlastrev(cr, uid, ids, context)
        else:
            docArray=ids
        return self._data_get_files(cr, uid, docArray, listedFiles, forceFlag, context)
        
    def GetAllFiles(self, cr, uid, request, default=None, context=None):
        """
            Extract documents to be returned 
        """
        forceFlag=False
        listed_models=[]
        listed_documents=[]
        modArray=[]
        oid, listedFiles, selection = request
        if selection == False:
            selection=1

        if selection<0:
            forceFlag=True
            selection=selection*(-1)

        kind='HiTree'                   # Get Hierarchical tree relations due to children
        docArray=self._explodedocs(cr, uid, oid, [kind], listed_models)
        
        if not oid in docArray:
            docArray.append(oid)        # Add requested document to package
                
        for item in docArray:
            kinds=['LyTree','RfTree']               # Get relations due to layout connected
            modArray.extend(self._relateddocs(cr, uid, item, kinds, listed_documents))
            modArray.extend(self._explodedocs(cr, uid, item, kinds, listed_documents))
#             kind='RfTree'               # Get relations due to referred connected
#             modArray.extend(self._relateddocs(cr, uid, item, kind, listed_documents))
#             modArray.extend(self._explodedocs(cr, uid, item, kind, listed_documents))

        modArray.extend(docArray)
        docArray=list(set(modArray))    # Get unique documents object IDs

        if selection == 2:
            docArray=self._getlastrev(cr, uid, docArray, context)
        
        if not oid in docArray:
            docArray.append(oid)     # Add requested document to package
        return self._data_get_files(cr, uid, docArray, listedFiles, forceFlag, context)

    def GetRelatedDocs(self, cr, uid, ids, default=None, context=None):
        """
            Extract documents related to current one(s) (layouts, referred models, etc.)
        """
        related_documents = []
        listed_documents = []
        read_docs = []
        for oid in ids:
            kinds = ['RfTree', 'LyTree']   # Get relations due to referred models
            read_docs.extend(self._relateddocs(cr, uid, oid, kinds, listed_documents, False))
            read_docs.extend(self._relatedbydocs(cr, uid, oid, kinds, listed_documents, False))
        documents = self.browse(cr, uid, read_docs, context=context)
        for document in documents:
            related_documents.append([document.id, document.name, document.preview, document.revisionid, document.description])
        return related_documents

    def getServerTime(self, cr, uid, oid, default=None, context=None):
        """
            calculate the server db time 
        """
        return datetime.now()
    
    def getLastTime(self, cr, uid, oid, default=None, context=None):
        """
            get document last modification time 
        """
        obj = self.browse(cr, uid, oid, context=context)
        if(obj.write_date!=False):
            return datetime.strptime(obj.write_date,'%Y-%m-%d %H:%M:%S')
        else:
            return datetime.strptime(obj.create_date,'%Y-%m-%d %H:%M:%S')

    def getUserSign(self, cr, uid, oid, default=None, context=None):
        """
            get the user name
        """
        userType=self.pool.get('res.users')
        uiUser=userType.browse(cr,uid,uid,context=context)
        return uiUser.name

    def _getbyrevision(self, cr, uid, name, revision):
        result=None
        results=self.search(cr,uid,[('name','=',name),('revisionid','=',revision)])
        for result in results:
            break
        return result

    def getCheckedOut(self, cr, uid, oid, default=None, context=None):
        checkoutType = self.pool.get('plm.checkout')
        checkoutIDs = checkoutType.search(cr,uid,[('documentid', '=', oid)])
        for checkoutID in checkoutIDs:
            objDoc = checkoutType.browse(cr,uid,checkoutID)
            return(objDoc.documentid.name,objDoc.documentid.revisionid,self.getUserSign(cr,objDoc.userid.id,1),objDoc.hostname)
        return ()

    def _file_delete(self, cr, uid, fname):
        '''
            Delete file only if is not saved on plm.backupdoc
        '''
        backupDocIds = self.pool.get('plm.backupdoc').search(cr, uid, [('existingfile', '=', fname)])
        if not backupDocIds:
            return super(plm_document, self)._file_delete(cr, uid, fname)

    def GetNextDocumentName(self, cr, uid, documentName, context={}):
        '''
        Return a new name due to sequence next number.
        '''
        nextDocNum = self.pool.get('ir.sequence').get(cr, uid, 'plm.document.progress')
        return documentName + '-' + nextDocNum

    @api.model
    def needUpdate(self):
        """
        check if the file need to be updated
        """
        checkoutIds = self.env['plm.checkout'].search([('documentid', '=', self.id),
                                                       ('userid', '=', self.env.uid)])
        for _brw in checkoutIds:
            return True
        return False

    @api.model
    def canBeSaved(self, raiseError=False):
        """
        check if the document can be saved and raise exception in case is not possible
        """
        msg = ''
        if self.state in ['released', 'obsoleted']:
            msg = _("Document is released and cannot be saved")
            if raiseError:
                raise UserError(msg)
        checkOutObject = self.getCheckOutObject()
        if checkOutObject:
            if checkOutObject.userid.id != self.env.uid:
                msg = _("Document is Check-Out from User %r", checkOutObject.name)
                if raiseError:
                    raise UserError(msg)
        else:
            msg = _("Document in check-In unable to save !")
            if raiseError:
                raise UserError(msg)
        if len(msg) > 0:
            return False, msg
        return True, ''

    @api.model
    def getCheckOutObject(self):
        checkoutIDs = self.env['plm.checkout'].search([('documentid', '=', self.id)])
        for checkoutID in checkoutIDs:
            return checkoutID
        return None

    @api.model
    def checkout(self, hostName, hostPws):
        """
        check out the current document
        """
        if self.is_checkout:
            raise UserError(_("Unable to check-Out a document that is already checked id by user %r" % self.checkout_user))
        if self.state in ['released', 'obsoleted']:
            raise UserError(_("Unable to check-Outcheck-Out a document that is in state %r" % self.state))
        values = {'userid': self.env.uid,
                  'hostname': hostName,
                  'hostpws': hostPws,
                  'documentid': self.id}
        self.env['plm.checkout'].create(values)

    @api.model
    def saveStructure(self, arguments):
        """
        save the structure passed
        self['FILE_PATH'] = ''
        self['PDF_PATH'] = ''
        self['PRODUCT_ATTRIBUTES'] = []
        self['DOCUMENT_ATTRIBUTES'] = []
        self['RELATION_ATTRIBUTES'] = []
        self['RELATIONS'] = [] # tutte le relazioni vanno qui ma devo metterci un attributo che mi identifica il tipo
                                # 2d2d 3d3d 3d2d o niente
        self['DOCUMENT_DATE'] = None
        """
        cPickleStructure, hostName, hostPws = arguments
        documentAttributes = {}
        documentRelations = {}
        productAttributes = {}
        productRelations = {}
        productDocumentRelations = {}
        objStructure = json.loads(cPickleStructure)

        documentAttribute = objStructure.get('DOCUMENT_ATTRIBUTES', {})
        for brwItem in self.search([('name', '=', documentAttribute.get('name', '')),
                                    ('revisionid', '=', documentAttribute.get('revisionid', -1))]):
            brwItem.canBeSaved(raiseError=True)

        def populateStructure(parentItem=False, structure={}):
            documentId = False
            productId = False
            documentProperty = structure.get('DOCUMENT_ATTRIBUTES', False)
            if documentProperty and structure.get('FILE_PATH', False):
                documentId = id(documentProperty)
                documentAttributes[documentId] = documentProperty
            productProperty = structure.get('PRODUCT_ATTRIBUTES', False)
            if productProperty:
                productId = id(productProperty)
                productAttributes[productId] = productProperty
            if productId and documentId:
                listRelated = productDocumentRelations.get(productId, [])
                listRelated.append(documentId)
                productDocumentRelations[productId] = listRelated
            if parentItem:
                parentDocumentId, parentProductId = parentItem
                relationAttributes = structure.get('MRP_ATTRIBUTES', {})
                childRelations = documentRelations.get(parentDocumentId, [])
                childRelations.append((documentId, relationAttributes.get('TYPE', '')))
                if parentDocumentId:
                    documentRelations[parentDocumentId] = childRelations
                if parentProductId:
                    if not documentId:
                        documentId = parentDocumentId
                    itemTuple = (productId, documentId, relationAttributes)
                    listItem = productRelations.get(parentProductId, [])
                    listItem.append(itemTuple)
                    productRelations[parentProductId] = listItem
            for subStructure in structure.get('RELATIONS', []):
                populateStructure((documentId, productId), subStructure)
        populateStructure(structure=objStructure)

        # Save the document
        logging.info("Savind Document")
        for documentAttribute in documentAttributes.values():
            documentAttribute['TO_UPDATE'] = False
            docId = False
            for brwItem in self.search([('name', '=', documentAttribute.get('name')),
                                        ('revisionid', '=', documentAttribute.get('revisionid'))]):
                if brwItem.state not in ['released', 'obsoleted']:
                    if brwItem.needUpdate():
                        brwItem.write(documentAttribute)
                        documentAttribute['TO_UPDATE'] = True
                docId = brwItem
            if not docId:
                docId = self.create(documentAttribute)
                docId.checkout(hostName, hostPws)
                documentAttribute['TO_UPDATE'] = True
            documentAttribute['id'] = docId.id

        # Save the product
        logging.info("Savind Product")
        productTemplate = self.env['product.product']
        for refId, productAttribute in productAttributes.items():
            linkedDocuments = set()
            for refDocId in productDocumentRelations.get(refId, []):
                linkedDocuments.add((4, documentAttributes[refDocId].get('id', 0)))
            prodId = False
            for brwItem in productTemplate.search([('engineering_code', '=', productAttribute.get('engineering_code')),
                                                   ('engineering_revision', '=', productAttribute.get('engineering_revision'))]):
                if brwItem.state not in ['released', 'obsoleted']:
                    brwItem.write(productAttribute)
                prodId = brwItem
                break
            if not prodId:
                if not productAttribute.get('name', False):
                    productAttribute['name'] = productAttribute.get('engineering_code', False)
                prodId = productTemplate.create(productAttribute)
            prodId.linkeddocuments
            if linkedDocuments:
                prodId.write({'linkeddocuments': list(linkedDocuments)})
            productAttribute['id'] = prodId.id
        # Save the document relation
        logging.info("Savind Document Relations")
        documentRelationTemplate = self.env['plm.document.relation']
        for parentId, childrenRelations in documentRelations.items():
            trueParentId = documentAttributes[parentId].get('id', 0)
            itemFound = set()
            for objBrw in documentRelationTemplate.search([('parent_id', '=', trueParentId)]):
                found = False
                for childId, relationType in childrenRelations:
                    trueChildId = documentAttributes.get(childId, {}).get('id', 0)
                    if objBrw.parent_id.id == trueParentId and objBrw.child_id.id == trueChildId and objBrw.type == relationType:
                        found = True
                        itemFound.add((childId, relationType))
                        break
                if not found:
                    objBrw.unlink()
            for childId, relationType in set(childrenRelations).difference(itemFound):
                trueChildId = documentAttributes.get(childId, {}).get('id', 0)
                documentRelationTemplate.create({'parent_id': trueParentId,
                                                 'child_id': trueChildId,
                                                 'type': relationType})
        # Save the product relation
        logging.info("Savind Product Relations")
        mrpBomTemplate = self.env['mrp.bom']
        for parentId, childRelations in productRelations.items():
            trueParentId = productAttributes[parentId].get('id')
            brwProduct = productTemplate.search([('id', '=', trueParentId)])
            productTempId = brwProduct.product_tmpl_id.id
            brwBoml = mrpBomTemplate.search([('product_tmpl_id', '=', productTempId)])
            if not brwBoml:
                brwBoml = mrpBomTemplate.create({'product_tmpl_id': productTempId,
                                                 'type': 'ebom'})
            # delete rows
            for _, documentId, _ in childRelations:
                trueDocumentId = documentAttributes.get(documentId, {}).get('id', 0)
                if trueDocumentId:  # sems strange this .. but i will delete only the bom with the right source id
                    for brwBom in brwBoml:
                        brwBom.deleteChildRow(trueDocumentId)
                    break
            # add rows
            for childId, documentId, relationAttributes in childRelations:
                if not (childId and documentId):
                    logging.warning("Bed relation request %r, %r" % (childId, documentId))
                    continue
                trueChildId = productAttributes[childId].get('id')
                trueDocumentId = documentAttributes[documentId].get('id')
                brwBom.addChildRow(trueChildId, trueDocumentId, relationAttributes)
        return json.dumps(objStructure)

plm_document()


class plm_checkout(models.Model):
    _name = 'plm.checkout'
    userid      =   fields.Many2one ('res.users', _('Related User'), ondelete='cascade')
    hostname    =   fields.Char     (_('hostname'),size=64)
    hostpws     =   fields.Char     (_('PWS Directory'),size=1024)
    documentid  =   fields.Many2one ('plm.document', _('Related Document'), ondelete='cascade')
    rel_doc_rev =   fields.Integer  (related='documentid.revisionid', string="Revision", store=True)

    _defaults = {
        'create_date': lambda self, ctx:time.strftime("%Y-%m-%d %H:%M:%S")
    }
    _sql_constraints = [
        ('documentid', 'unique (documentid)', _('The documentid must be unique !'))
    ]

    def _adjustRelations(self, cr, uid, oids, userid=False):
        docRelType=self.pool.get('plm.document.relation')
        if userid:
            ids=docRelType.search(cr,uid,[('child_id','in',oids),('userid','=',False)])
        else:
            ids=docRelType.search(cr,uid,[('child_id','in',oids)])
        if ids:
            values={'userid':userid,}
            docRelType.write(cr, uid, ids, values)

    def create(self, cr, uid, vals, context=None):
        documentType=self.pool.get('plm.document')
        docID=documentType.browse(cr, uid, vals['documentid'])
        values={'writable':True,}
        if not documentType.write(cr, uid, [docID.id], values):
            logging.warning("create : Unable to check-out the required document ("+str(docID.name)+"-"+str(docID.revisionid)+").")
            raise UserError( _("Unable to check-out the required document ("+str(docID.name)+"-"+str(docID.revisionid)+")."))
            return False
        self._adjustRelations(cr, uid, [docID.id], uid)
        newID = super(plm_checkout,self).create(cr, uid, vals, context=context)   
        documentType.wf_message_post(cr, uid, [docID.id], body=_('Checked-Out'))
        return newID

    def unlink(self, cr, uid, ids, context=None):
        documentType = self.pool.get('plm.document')
        checkObjs = self.browse(cr, uid, ids, context=context)
        docids = []
        for checkObj in checkObjs:
            checkObj.documentid.writable = False
            values = {'writable': False}
            docids.append(checkObj.documentid.id)
            if not documentType.write(cr, uid, [checkObj.documentid.id], values):
                logging.warning("unlink : Unable to check-in the document (" + str(checkObj.documentid.name)+"-"+str(checkObj.documentid.revisionid)+").\n You can't change writable flag.")
                raise UserError(_("Unable to Check-In the document (" + str(checkObj.documentid.name)+"-"+str(checkObj.documentid.revisionid)+").\n You can't change writable flag."))
                return False
        self._adjustRelations(cr, uid, docids, False)
        dummy = super(plm_checkout, self).unlink(cr, uid, ids, context=context)
        if dummy:
            documentType.wf_message_post(cr, uid, docids, body=_('Checked-In'))
        return dummy

plm_checkout()


class plm_document_relation(models.Model):
    _name = 'plm.document.relation'
    
    parent_id       =   fields.Many2one ('plm.document', _('Related parent document'), ondelete='cascade')
    child_id        =   fields.Many2one ('plm.document', _('Related child document'),  ondelete='cascade')
    configuration   =   fields.Char     (_('Configuration Name'),size=1024)
    link_kind       =   fields.Char     (_('Kind of Link'),size=64, required=True)  # LyTree or HiTree or RfTree
    create_date     =   fields.Datetime (_('Date Created'), readonly=True)

    #  TODO: To remove userid field for version 10
    userid          =   fields.Many2one ('res.users', _('CheckOut User'),readonly="True")
    
    _defaults = {
                 'link_kind': lambda *a: 'HiTree',
                 'userid': lambda *a: False,
    }
    _sql_constraints = [
        ('relation_uniq', 'unique (parent_id,child_id,link_kind)', _('The Document Relation must be unique !')) 
    ]

    def deleteRelation(self, parentId, childId, kind, configuration=False):
        """
            controllare se la configurazione e; usata !!!!!
        """
        # TODO: da dare
        pass

    def SaveStructure(self, cr, uid, relations, level=0, currlevel=0):
        """
            Save Document relations
        """
        def cleanStructure(relations):
            res={}
            cleanIds=[]
            for relation in relations:
                res['parent_id'],res['child_id'],res['configuration'],res['link_kind']=relation
                link=[('link_kind','=',res['link_kind'])]
                if (res['link_kind']=='LyTree') or (res['link_kind']=='RfTree'):
                    criteria=[('child_id','=',res['child_id'])]
                else:
                    criteria=[('parent_id','=',res['parent_id']),('child_id','=',res['child_id'])]
                cleanIds.extend(self.search(cr,uid,criteria+link))
            self.unlink(cr,uid,list(set(cleanIds)))

        def saveChild(relation):
            """
                save the relation
            """
            try:
                res={}
                res['parent_id'],res['child_id'],res['configuration'],res['link_kind']=relation
                if (res['parent_id']!= None) and (res['child_id']!=None):
                    if (len(str(res['parent_id']))>0) and (len(str(res['child_id']))>0):
                        if not((res['parent_id'],res['child_id']) in savedItems):
                            savedItems.append((res['parent_id'],res['child_id']))
                            self.create(cr, uid, res)
                else:
                    logging.error("saveChild : Unable to create a relation between documents. One of documents involved doesn't exist. Arguments(" + str(relation) +") ")
                    raise Exception(_("saveChild: Unable to create a relation between documents. One of documents involved doesn't exist."))
            except Exception,ex:
                logging.error("saveChild : Unable to create a relation. Arguments (%s) Exception (%s)" %(str(relation), str(ex)))
                raise Exception(_("saveChild: Unable to create a relation."))
            
        savedItems=[]
        if len(relations)<1: # no relation to save 
            return False
        cleanStructure(relations)
        for relation in relations:
            saveChild(relation)
        return False

plm_document_relation()
