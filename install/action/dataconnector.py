
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
import os
import types
import cPickle as pickle
from datetime import datetime
from sqlalchemy import *

from osv import osv, fields
import logging


class plm_component(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'

###################################################################
#   Override these properties to configure TransferData process.  #
###################################################################

    @property
    def get_part_data_transfer(self):
        """
            Map OpenErp vs. destination Part data transfer fields
        """
        return {
                'name'                  : 'revname',
                'engineering_revision'  : 'revprog',
                'description'           : 'revdes',
                }

    @property
    def get_status_data_transfer(self):
        """
            Map OpenErp vs. destination Part data transfer fields
        """
        return [
                'released',
               ]

    @property
    def get_bom_data_transfer(self):
        """
            Map OpenErp vs. destination BoM data transfer fields
        """
        return {
                'itemnum'               : 'relpos',
                'product_qty'           : 'relqty',
                }

    @property
    def get_data_transfer(self):
        """
            Map OpenErp vs. destination Connection DB data transfer values
        """
        return {
                'db':
                    {
                    'protocol'              : 'mssql+pymssql',
                    'user'                  : 'dbamkro',
                    'password'              : 'dbamkro',
                    'host'                  : 'SQL2K8\SQLEXPRESS',
                    'database'              : 'Makro',
                    },
                
                'file':
                    {
                    'exte'                  : 'csv',
                    'separator'             : ',',
                    'name'                  : 'transfer',
                    'bomname'               : 'tranferbom',
                    'directory'             : '/tmp',
                    }
                }

###################################################################
#   Override these properties to configure TransferData process.  #
###################################################################

    @property
    def get_last_session(self):
        """
            Get last execution date & time as stored.
                format => '%Y-%m-%d %H:%M:%S'
        """
        lastDate=datetime.now()
        fileName=os.path.join(os.environ.get('HOME'),'ttsession.time')
        if os.path.exists(fileName):
            try:
                fobj=open(fileName)
                lastDate=pickle.load(fobj)
                fobj.close()
            except:
                try:
                    fobj.close()
                except:
                    pass
                os.unlink(fileName)
        return lastDate.strftime('%Y-%m-%d %H:%M:%S')

    @property
    def set_last_session(self):
        """
            Get last execution date & time as stored.
                format => '%Y-%m-%d %H:%M:%S'
        """
        lastDate=datetime.now()
        fileName=os.path.join(os.environ.get('HOME'),'ttsession.time')
        if os.path.exists(fileName):
            os.unlink(fileName)
        fobj=open(fileName,'w')
        pickle.dump(lastDate,fobj)
        fobj.close()
        return lastDate.strftime('%Y-%m-%d %H:%M:%S')

    @property
    def get_connection(self,dataConn):
        """
            Get last execution date & time as stored.
                format => '%Y-%m-%d %H:%M:%S'
        """
        connection=False
        try:
            connectionString=r'%s://%s:%s@%s/%s' %(dataConn['protocol'],dataConn['user'],dataConn['password'],dataConn['host'],dataConn['database'])
            engine = create_engine(connectionString, echo=False)
            connection = engine.connect()
        except Exception,ex:
            logging.error("[get_connection] : Error to connect (%s)." %(str(ex)))
        return connection
    
    def TransferData(self, cr, uid, ids=False, context=None):
 
        updateDate=self.get_last_session
        logging.debug("[TransferData] Start : %s" %(str(updateDate)))
        transfer=self.get_data_transfer
        datamap=self.get_part_data_transfer
        fieldsListed=datamap.keys()
        statuses=self.get_status_data_transfer
        allIDs=self.query_data(cr, uid, updateDate)
        tmpData=self.export_data(cr, uid, allIDs, fieldsListed)
        if tmpData.get('datas'):
            if 'db' in transfer:
                connection=self.get_connection(transfer['db'])
            
                checked=self.saveParts(cr, uid, connection, tmpData.get('datas'), fieldsListed, datamap)
    
                if checked:
                    self.saveBoms(cr, uid, connection, checked, allIDs, fieldsListed, datamap)   
                if connection:
                    connection.quit()
            if 'file' in transfer:
                datamap=self.get_bom_data_transfer
                bomfieldsListed=datamap.keys()
                self.extract_data(cr,uid,ids,allIDs, fieldsListed, bomfieldsListed,transfer['db'])

        updateDate=self.set_last_session
        logging.debug("[TransferData] End : %s" %(str(updateDate)))
        return False

    def query_data(self, cr, uid, updateDate):
        """
            Query to return values based on columns selected.
                updateDate => '%Y-%m-%d %H:%M:%S'
        """
        allIDs=self.search(cr,uid,[('write_date','>',updateDate),('state','in',['released'])],order='engineering_revision')
        allIDs.extend(self.search(cr,uid,[('create_date','>',updateDate),('state','in',['released'])],order='engineering_revision'))
        return list(set(allIDs))

    def saveParts(self, cr, uid, connection, prtInfos, fieldsListed, datamap):
        """
            Updates parts if exist in DB otherwise it create them.
        """
        checked={}
        if connection:
            for prtInfo in prtInfos:
                entity=False
                prtDict=dict(zip(fieldsListed,prtInfo))
                if 'TMM_COMPONENT' in prtDict:
                    kindName=prtDict['TMM_COMPONENT']
                else:
                    kindName='COMPONENT'
                if 'name' in prtDict:
                    prtName=prtDict['name']
                else:
                    continue
                        
                filterString="RevName = '%s'" %(prtName)
                try:
                    for ent in connection.entities.query(kindName, filterSql=filterString):
                        entity = ent
                        break
                    if not entity:
                        entity=connection.entities.create(kindName)

                    for column in prtDict.keys():
                        entity.setValue(datamap[column],prtDict[column])
                    connection.entities.save(entity)
                    checked[prtName]=entity
                except Exception:
                    checked[prtName]=False
        return checked

    def saveBoms(self, cr, uid, connection, checked, allIDs, fieldsListed, datamap):

        
        def checkChildren(self, cr, uid, connection, components, datamap):
            for component in components:
                for bomid in component.bom_ids:
                    if not (str(bomid.type).upper()==kindName):
                        continue
                    for bom in bomid.bom_lines:
                        if not bom.product_id.name in childNames:
                            childNames.append(bom.product_id.name)
                            childIDs.append(bom.product_id.id)
                            
            tmpData=self.export_data(cr, uid, childIDs, datamap.keys())
            return self.saveParts(cr, uid, connection, tmpData.get('datas'), fieldsListed, datamap)

        def removeBoms(connection, parentName, kindName, relSource):
            filterString="RelParent ='%s' and Relsource='%s' and TMM_TYPE='%s'" %(parentName,relSource,kindName)
            for relation in connection.entities.query("RELATION", filterSql=filterString):
                if connection.relations.isDeletable(relation,kindName):
                    connection.relations.delete(relation)


        kindName='EBOM'
        relation=False
        childNames=[]
        childIDs=[]
        entityChecked=checked
        
        if connection:
                    
            components=self.browse(cr, uid, allIDs)

            entityChecked.update(checkChildren(self, cr, uid, connection, components, datamap))
                             
            for component in components:
                if not component.name in entityChecked.keys():
                    continue
                entityFather=entityChecked[component.name]
                for bomid in component.bom_ids:
                    if not (str(bomid.type).upper()==kindName):
                        continue
                    relSource=bomid.source_id.name
                    
                    removeBoms(connection, component.name, kindName, relSource)

                    for bom in bomid.bom_lines:
                        if not bom.product_id.name in entityChecked.keys():
                            continue
                        entityChild=entityChecked[bom.product_id.name]
                        relation=connection.relations.create(entityFather, entityChild, kindName)
                        
                        bomFields=self.get_bom_data_transfer
                        expData=self.pool.get('mrp.bom').export_data(cr, uid, [bom.id], bomFields.keys())
                        if expData.get('datas'):
                            bomData=dict(zip(bomFields.values(),expData.get('datas')[0]))                                       
                            for column in bomData:
                                relation.setValue(column,bomData[column])
                        relation.setValue('RelSource',relSource)
                        connection.relations.save(relation,forceNew=True)


    def extract_data(self,cr,uid,ids,allIDs, anag_fields=False, rel_fields=False, transferdata={}):
        """
            action to be executed for Transmitted state.
            Transmit the object to ERP Metodo
        """
        if not anag_fields:
            anag_fields=['name','description']
        if not rel_fields:
            rel_fields=['bom_id','product_id','product_qty','itemnum']

        if not transferdata:
            outputpath=os.environ.get('TEMP')
            tmppws=os.environ.get('OPENPLMOUTPUTPATH')
            if tmppws!=None and os.path.exists(tmppws):
                outputpath=tmppws
            exte='csv'
            fname=datetime.now().isoformat(' ').replace('.','').replace(':','').replace(' ','').replace('-','')+'.'+exte
            bomname="bom"
        else:
            outputpath=transferdata['directory']
            exte="%s" %(str(transferdata['exte']))
            fname="%s.%s" %(str(transferdata['name']),exte)
            bomname="%s" %(str(transferdata['bomname']))
            
        if outputpath==None:
            return True
        if not os.path.exists(outputpath):
            raise osv.except_osv(_('Export Data Error'), _("Requested writing path (%s) doesn't exist." %(outputpath)))
            return False 

        filename=os.path.join(outputpath,fname)
        expData=self.export_data(cr, uid, allIDs,anag_fields)
        if not self.export_csv(filename, anag_fields, expData, True):
            raise osv.except_osv(_('Export Data Error'), _("Writing operations on file (%s) have failed." %(filename)))
            return False
        bomType=self.pool.get('mrp.bom')
        for oic in self.browse(cr, uid, ids, context=None):
            fname="%s-%s.%s" %(bomname,str(oic.name),exte)
            filename=os.path.join(outputpath,fname)
            relIDs=self._getExplodedBom(cr, uid, [oic.id], 1, 0)
            if len(relIDs)>0:
                expData=bomType.export_data(cr, uid, relIDs,rel_fields)
                if not self.export_csv(filename, rel_fields, expData, True):
                    raise osv.except_osv(_('Export Data Error'), _("No Bom extraction files was generated, about entity (%s)." %(fname)))
                    return False
        return True

    def export_csv(self, fname, fields=[], result={}, write_title=False):
        import csv
        if not ('datas' in result) or not result:
            logging.error("export_csv : No 'datas' in result.")
            return False

        if not fields:
            logging.error("export_csv : No 'fields' in result.")
            return False
        
        try:
            fp = file(fname, 'wb+')
            writer = csv.writer(fp)
            if write_title:
                writer.writerow(fields)
            results=result['datas']
            for datas in results:
                row = []
                for data in datas:
                    if type(data)==types.StringType:
                        row.append(data.replace('\n',' ').replace('\t',' '))
                    else:
                        row.append(data or '')
                writer.writerow(row)
            fp.close()
            return True
        except IOError, (errno, strerror):
            logging.error("export_csv : IOError : "+str(errno)+" ("+str(strerror)+").")
            return False


plm_component()


