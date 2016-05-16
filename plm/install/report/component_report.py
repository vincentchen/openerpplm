 # -*- coding: utf-8 -*-
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
from datetime import datetime
from dateutil import tz

from book_collector import BookCollector,packDocuments
from openerp.report.interface import report_int
from openerp import pooler

def getBottomMessage(user, context):
        to_zone = tz.gettz(context.get('tz', 'Europe/Rome'))
        from_zone = tz.tzutc()
        dt = datetime.now()
        dt = dt.replace(tzinfo=from_zone)
        localDT = dt.astimezone(to_zone)
        localDT = localDT.replace(microsecond=0)
        return "Printed by " + str(user.name) + " : " + str(localDT.ctime())

class component_custom_report(report_int):
    """
        Return a pdf report of each printable document attached to given Part ( level = 0 one level only, level = 1 all levels)
    """
    def create(self, cr, uid, ids, datas, context=None):
        self.pool = pooler.get_pool(cr.dbname)
        docRepository=self.pool.get('plm.document')._get_filestore(cr)
        componentType=self.pool.get('product.product')
        user=self.pool.get('res.users').browse(cr, uid, uid, context=context)
        msg = getBottomMessage(user, context)
        output  = BookCollector(jumpFirst=False,customTest=(False, msg),bottomHeight=10, poolObj=self.pool, cr=cr, uid=uid)
        documents=[]
        components=componentType.browse(cr, uid, ids, context=context)
        for component in components:
            documents.extend(component.linkeddocuments)
        return packDocuments(docRepository,documents,output)

component_custom_report('report.product.product.pdf')

class component_one_custom_report(report_int):
    """
        Return a pdf report of each printable document attached to children in a Bom ( level = 0 one level only, level = 1 all levels)
    """
    def create(self, cr, uid, ids, datas, context=None):
        self.pool = pooler.get_pool(cr.dbname)
        docRepository=self.pool.get('plm.document')._get_filestore(cr)
        componentType=self.pool.get('product.product')
        user=self.pool.get('res.users').browse(cr, uid, uid, context=context)
        msg = getBottomMessage(user, context)
        output  = BookCollector(jumpFirst=False,customTest=(False, msg),bottomHeight=10, poolObj=self.pool, cr=cr, uid=uid)
        children=[]
        documents=[]
        components=componentType.browse(cr, uid, ids, context=context)
        for component in components:
            documents.extend(component.linkeddocuments)
            idcs = componentType._getChildrenBom(cr, uid, component, 0, 1, context=context)
            children=componentType.browse(cr, uid, idcs, context=context)
            for child in children:
                documents.extend(child.linkeddocuments)
        return packDocuments(docRepository,list(set(documents)),output)

component_one_custom_report('report.one.product.product.pdf')

class component_all_custom_report(report_int):
    """
        Return a pdf report of each printable document attached to children in a Bom ( level = 0 one level only, level = 1 all levels)
    """
    def create(self, cr, uid, ids, datas, context=None):
        self.pool = pooler.get_pool(cr.dbname)
        docRepository=self.pool.get('plm.document')._get_filestore(cr)
        componentType=self.pool.get('product.product')
        user=self.pool.get('res.users').browse(cr, uid, uid, context=context)
        msg = getBottomMessage(user, context)
        output  = BookCollector(jumpFirst=False,customTest=(False,msg),bottomHeight=10, poolObj=self.pool, cr=cr, uid=uid)
        children=[]
        documents=[]
        components=componentType.browse(cr, uid, ids, context=context)
        for component in components:
            documents.extend(component.linkeddocuments)
            idcs=componentType._getChildrenBom(cr, uid, component, 1, context=context)
            children=componentType.browse(cr, uid, idcs, context=context)
            for child in children:
                documents.extend(child.linkeddocuments)
        return packDocuments(docRepository,list(set(documents)),output)

component_all_custom_report('report.all.product.product.pdf')
