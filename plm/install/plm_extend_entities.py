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
import time
from openerp.osv import osv, fields
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT

def _moduleName():
    path = os.path.dirname(__file__)
    return os.path.basename(os.path.dirname(path))
openerpModule=_moduleName()

class plm_document(osv.osv):
    _name = 'plm.document'
    _inherit = ['mail.thread','plm.document']
    _columns = {
                'linkedcomponents':fields.many2many('product.product', 'plm_component_document_rel','document_id','component_id', 'Linked Parts'),
    }    
    _defaults = {
                 'state': lambda *a: 'draft',
                 'res_id': lambda *a: False,
    }    
plm_document()


class plm_component(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'
    
    def _father_part_compute(self, cr, uid, ids, name, arg, context={}):
        """ Gets father bom.
        @param self: The object pointer
        @param cr: The current row, from the database cursor,
        @param uid: The current user ID for security checks
        @param ids: List of selected IDs
        @param name: Name of the field
        @param arg: User defined argument
        @param context: A standard dictionary for contextual values
        @return:  Dictionary of values
        """
        result={}
        if context is None:
            context = {}
        bom_line_objType = self.pool.get('mrp.bom.line')
        prod_objs = self.browse(cr, uid, ids, context=context)
        for prod_obj in prod_objs:
            prod_ids = []
            bom_line_ids = bom_line_objType.search(cr, uid, [('product_id', '=', prod_obj.id)])
            for bom_line_obj in bom_line_objType.browse(cr, uid, bom_line_ids, context=context):
                prodIds = self.search(cr, uid, [('product_tmpl_id', '=', bom_line_obj.bom_id.product_tmpl_id.id)])
                prod_ids.extend(prodIds)
            result[prod_obj.id] = list(set(prod_ids))
        return result

  
    _columns = {
        	    'linkeddocuments':fields.many2many('plm.document', 'plm_component_document_rel','component_id','document_id', 'Linked Docs'),  
                'tmp_material': fields.many2one('plm.material','Raw Material', required=False, change_default=True, help="Select raw material for current product"),
#                'tmp_treatment': fields.many2one('plm.treatment','Thermal Treatment', required=False, change_default=True, help="Select thermal treatment for current product"),
                'tmp_surface': fields.many2one('plm.finishing','Surface Finishing', required=False, change_default=True, help="Select surface finishing for current product"),
                'father_part_ids': fields.function(_father_part_compute, relation='product.product', method=True, string="BoM Hierarchy", type='many2many', store =False),
              }

    def on_change_tmpmater(self, cr, uid, ids, tmp_material=False):
        values={'engineering_material':''}
        if tmp_material:
            thisMaterial=self.pool.get('plm.material')
            thisObject=thisMaterial.browse(cr, uid, tmp_material)
            if thisObject.name:
                values['engineering_material']=thisObject.name
        return {'value': {'engineering_material':str(values['engineering_material'])}}

    def on_change_tmptreatment(self, cr, uid, ids, tmp_treatment=False):
        values={'engineering_treatment':''}
        if tmp_treatment:
            thisTreatment=self.pool.get('plm.treatment')
            thisObject=thisTreatment.browse(cr, uid, tmp_treatment)
            if thisObject.name:
                values['engineering_treatment']=thisObject.name
        return {'value': {'engineering_treatment':str(values['engineering_treatment'])}}

    def on_change_tmpsurface(self, cr, uid, ids, tmp_surface=False):
        values={'engineering_surface':''}
        if tmp_surface:
            thisSurface=self.pool.get('plm.finishing')
            thisObject=thisSurface.browse(cr, uid, tmp_surface)
            if thisObject.name:
                values['engineering_surface']=thisObject.name
        return {'value': {'engineering_surface':str(values['engineering_surface'])}}
plm_component()


class plm_relation(osv.osv):
    _name = 'mrp.bom'
    _inherit = 'mrp.bom'

#######################################################################################################################################33

#   Overridden methods for this entity

    def _bom_find(self, cr, uid, product_tmpl_id=None, product_id=None, properties=None, context=None):
        """ Finds BoM for particular product and product uom.
        @param product_tmpl_id: Selected product.
        @param product_uom: Unit of measure of a product.
        @param properties: List of related properties.
        @return: False or BoM id.
        """
        bom_id = super(plm_relation, self)._bom_find(cr,
                                                                                     uid,
                                                                                     product_tmpl_id=product_tmpl_id,
                                                                                     product_id=product_id,
                                                                                     properties=properties,
                                                                                     context=context)
        if bom_id:
            objBom = self.browse(cr, uid, bom_id, context)
            odooPLMBom = ['ebom', 'spbom']
            if objBom.type in odooPLMBom:
                bom_ids = self.search(cr, uid, [('product_id', '=', objBom.product_id.id),
                                                ('product_tmpl_id', '=', objBom.product_tmpl_id.id),
                                                ('type', 'not in', odooPLMBom)])
                for _id in bom_ids:
                    return _id
        return bom_id
    
#######################################################################################################################################33

    def _father_compute(self, cr, uid, ids, name, arg, context=None):
        """ Gets father bom.
        @param self: The object pointer
        @param cr: The current row, from the database cursor,
        @param uid: The current user ID for security checks
        @param ids: List of selected IDs
        @param name: Name of the field
        @param arg: User defined argument
        @param context: A standard dictionary for contextual values
        @return:  Dictionary of values
        """
        bom_type=''
        result = {}
        if context is None:
            context = {}
        bom_objType = self.pool.get('mrp.bom')
        bom_line_objType = self.pool.get('mrp.bom.line')
        bom_objs = bom_objType.browse(cr, uid, ids, context=context)
        for bom_obj in bom_objs:
            bom_type=bom_obj.type
            result[bom_obj.id]=[]
            for thisId in ids:
                if bom_type=='':
                    tmp_ids = bom_line_objType.search(cr, uid, [('product_id','=',bom_obj.product_id.id)])
                else:
                    tmp_ids = bom_line_objType.search(cr, uid, [('product_id','=',bom_obj.product_id.id),('type','=',bom_type)])
            
                bom_children = bom_line_objType.browse(cr, uid, list(set(tmp_ids)), context=context)
                for bom_child in bom_children:
                    if bom_child.bom_id.id:
                        if not(bom_child.bom_id.id in result[bom_obj.id]):
                            result[bom_obj.id]+=[bom_child.bom_id.id]
        return result
 
    _columns = {
                'state': fields.related('product_id','state',type="char",relation="product.template",string="Status",help="The status of the product in its LifeCycle.",store=False),
                'engineering_revision': fields.related('product_id','engineering_revision',type="char",relation="product.template",string="Revision",help="The revision of the product.",store=False),
                'description': fields.related('product_id','description',type="char",relation="product.template",string="Description",store=False),
                'father_complete_ids': fields.function(_father_compute, relation='mrp.bom', method=True, string="BoM Hierarchy", type='many2many', store =False),
               }

plm_relation()

class plm_relation_line(osv.osv):
    _name = 'mrp.bom.line'
    _inherit = 'mrp.bom.line'
    _order = "itemnum"

    def _get_child_bom_lines(self, cr, uid, ids, field_name, arg, context=None):
        """
            If the BOM line refers to a BOM, return the ids of the child BOM lines
        """
        bom_obj = self.pool.get('mrp.bom')
        res = {}
        for bom_line in self.browse(cr, uid, ids, context=context):
            for bom_id in bom_obj.search(cr, uid, [('product_id', '=', bom_line.product_id.id),
                                      ('product_tmpl_id', '=', bom_line.product_id.product_tmpl_id.id),
                                      ('type', '=', bom_line.type)]):
                child_bom = bom_obj.browse(cr, uid, bom_id, context=context)
                res[bom_line.id] = [x.id for x in child_bom.bom_line_ids]
            else:
                res[bom_line.id] = False
        return res

    _columns = {
                'state': fields.related('product_id','state',type="char",relation="product.template",string="Status",help="The status of the product in its LifeCycle.",store=False),
                'engineering_revision': fields.related('product_id','engineering_revision',type="char",relation="product.template",string="Revision",help="The revision of the product.",store=False),
                'description': fields.related('product_id','description',type="char",relation="product.template",string="Description",store=False),
                'weight_net': fields.related('product_id','weight_net',type="float",relation="product.template",string="Weight Net",store=False),
                'child_line_ids': fields.function(_get_child_bom_lines, relation="mrp.bom.line", string="BOM lines of the referred bom", type="one2many"),
               }

plm_relation_line()

class plm_document_relation(osv.osv):
    _name = 'plm.document.relation'
    _inherit = 'plm.document.relation'
    _columns = {
                'parent_preview': fields.related('parent_id','preview',type="binary",relation="plm.document",string="Preview",store=False),
                'parent_state': fields.related('parent_id','state',type="char",relation="plm.document",string="Status",store=False),
                'parent_revision': fields.related('parent_id','revisionid',type="integer",relation="plm.document",string="Revision",store=False),
                'parent_checkedout': fields.related('parent_id','checkout_user',type="char",relation="plm.document",string="Checked-Out To",store=False),
                'child_preview': fields.related('child_id','preview',type="binary",relation="plm.document",string="Preview",store=False),
                'child_state': fields.related('child_id','state',type="char",relation="plm.document",string="Status",store=False),
                'child_revision': fields.related('child_id','revisionid',type="integer",relation="plm.document",string="Revision",store=False),
                'child_checkedout': fields.related('child_id','checkout_user',type="char",relation="plm.document",string="Checked-Out To",store=False),
              }
plm_document_relation()

