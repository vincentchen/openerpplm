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

import sys
import types
import logging
import copy
import openerp.addons.decimal_precision as dp
from openerp        import models
from openerp        import fields
from openerp        import api
from openerp        import SUPERUSER_ID
from openerp        import _
from openerp        import osv
from openerp.exceptions import UserError
_logger         =   logging.getLogger(__name__)

# To be adequated to plm.document class states
USED_STATES = [('draft', _('Draft')),
               ('confirmed', _('Confirmed')),
               ('released', _('Released')),
               ('undermodify', _('UnderModify')),
               ('obsoleted', _('Obsoleted'))]


class plm_config_settings(models.Model):
    _name = 'plm.config.settings'
    _inherit = 'res.config.settings'

    module_plm_automatic_weight = fields.Boolean("Plm Automatic Weight")
    module_plm_cutted_parts = fields.Boolean("Plm Cutted Parts")
    module_plm_pack_and_go = fields.Boolean("Plm Pack and go")
    module_product_description_language_helper = fields.Boolean("Plm Product Description Language Helper")
    module_plm_report_language_helper = fields.Boolean("Plm Report Language Helper")
    module_plm_automate_nbom = fields.Boolean("Plm Automate Normal Bom")
    module_plm_date_bom = fields.Boolean("Plm Date Bom")
    module_plm_web_revision = fields.Boolean("Plm Web Revision")
    module_plm_auto_internalref = fields.Boolean("Populate internal reference with engineering infos")

plm_config_settings()


class plm_component(models.Model):
    _name = 'product.template'
    _inherit = 'product.template'

    state                   =   fields.Selection(USED_STATES, _('Status'), help=_("The status of the product in its LifeCycle."), readonly="True")
    engineering_code        =   fields.Char(_('Part Number'), help=_("This is engineering reference to manage a different P/N from item Name."), size=64)
    engineering_revision    =   fields.Integer(_('Revision'), required=True, help=_("The revision of the product."))
    engineering_writable    =   fields.Boolean(_('Writable'))
    engineering_material    =   fields.Char(_('Raw Material'), size=128, required=False, help=_("Raw material for current product, only description for titleblock."))

    #engineering_treatment    =    fields.Char        (_('Treatment'),size=64,required=False,help=_("Thermal treatment for current product"))
    engineering_surface     =   fields.Char(_('Surface Finishing'), size=128, required=False, help=_("Surface finishing for current product, only description for titleblock."))

#   Internal methods
    @api.multi
    def engineering_products_open(self):
        product_id = False
        relatedProductBrwsList = self.env['product.product'].search([('product_tmpl_id', '=', self.id)])
        for relatedProductBrws in relatedProductBrwsList:
            product_id = relatedProductBrws.id
        mod_obj = self.env['ir.model.data']
        search_res = mod_obj.get_object_reference('plm', 'plm_component_base_form')
        form_id = search_res and search_res[1] or False
        if product_id and form_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Product Engineering'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'product.product',
                'res_id': product_id,
                'views': [(form_id, 'form')],
            }

    _defaults = {
                 'state': lambda *a: 'draft',
                 #'engineering_revision': lambda self,ctx:0,
                 #'engineering_writable': lambda *a: True,
                 'engineering_revision': 0,
                 'engineering_writable': True,
                 'type': 'product',
                 'standard_price': 0,
                 'volume': 0,
                 'weight': 0,
                 'cost_method': 0,
                 'sale_ok': 0,
                 'state': 'draft',
                 'mes_type': 'fixed',
                 'cost_method': 'standard',
    }
    _sql_constraints = [
        ('partnumber_uniq', 'unique (engineering_code,engineering_revision)', _('Part Number has to be unique!'))
    ]

    def init(self, cr):
        cr.execute("""
-- Index: product_template_engcode_index

DROP INDEX IF EXISTS product_template_engcode_index;

CREATE INDEX product_template_engcode_index
  ON product_template
  USING btree
  (engineering_code);
  """)

        cr.execute("""
-- Index: product_template_engcoderev_index

DROP INDEX IF EXISTS product_template_engcoderev_index;

CREATE INDEX product_template_engcoderev_index
  ON product_template
  USING btree
  (engineering_code, engineering_revision);
  """)

plm_component()


class plm_component_document_rel(models.Model):
    _name = 'plm.component.document.rel'
    _description = "Component Document Relations"

    component_id    =   fields.Many2one('product.product', _('Linked Component'), ondelete='cascade')
    document_id     =   fields.Many2one('plm.document', _('Linked Document'), ondelete='cascade')

    _sql_constraints = [
        ('relation_unique', 'unique(component_id,document_id)', _('Component and Document relation has to be unique !')),
    ]

    def SaveStructure(self, cr, uid, relations, level=0, currlevel=0):
        """
            Save Document relations
        """
        def cleanStructure(relations):
            res = []
            for document_id, component_id in relations:
                latest = (document_id, component_id)
                if latest in res:
                    continue
                res.append(latest)
                ids = self.search(cr, uid, [('document_id', '=', document_id), ('component_id', '=', component_id)])
                if ids:
                    self.unlink(cr, uid, ids)

        def saveChild(args):
            """
                save the relation
            """
            try:
                res = {}
                res['document_id'], res['component_id'] = args
                self.create(cr, uid, res)
            except:
                logging.warning("saveChild : Unable to create a link. Arguments (%s)." % (str(args)))
                raise Exception(_("saveChild: Unable to create a link."))

        if len(relations) < 1:  # no relation to save
            return False
        cleanStructure(relations)
        for relation in relations:
            saveChild(relation)
        return False

plm_component_document_rel()


class plm_relation_line(models.Model):
    _name = 'mrp.bom.line'
    _inherit = 'mrp.bom.line'


    @api.multi
    def openRelatedDocuments(self):
        domain = [('id', 'in', self.related_document_ids.ids)]
        outActDict = {'name': _('Documents'),
                      'view_type': 'form',
                      'res_model': 'plm.document',
                      'type': 'ir.actions.act_window',
                      'view_mode': 'tree,form'}
        outActDict['domain'] = domain
        return outActDict
        
    @api.multi
    def _related_doc_ids(self):
        for bomLineBrws in self:
            bomLineBrws.related_document_ids = bomLineBrws.product_id.linkeddocuments

    create_date     = fields.Datetime(_('Creation Date'), readonly=True)
    source_id       = fields.Many2one('plm.document', 'name', ondelete='no action', readonly=True, help=_("This is the document object that declares this BoM."))
    type            = fields.Selection([('normal', _('Normal BoM')), ('phantom', _('Sets / Phantom')), ('ebom', _('Engineering BoM')), ('spbom', _('Spare BoM'))], _('BoM Type'), required=True, help=
        _("Phantom BOM: When processing a sales order for this product, the delivery order will contain the raw materials, instead of the finished product." \
        " Ship this product as a set of components (kit)."))
    itemnum         = fields.Integer(_('CAD Item Position'), help=_("This is the item reference position into the CAD document that declares this BoM."))
    itemlbl         = fields.Char(_('CAD Item Position Label'), size=64)
    ebom_source_id  = fields.Integer('Source Ebom ID')
    related_document_ids = fields.One2many(compute='_related_doc_ids', comodel_name='plm.document', string=_('Related Documents'))
 
    _defaults = {
        'product_uom': 1,
    }

    _order = 'itemnum'

plm_relation_line()


class plm_relation(models.Model):
    _name = 'mrp.bom'
    _inherit = 'mrp.bom'

    create_date      =   fields.Datetime(_('Creation Date'), readonly=True)
    source_id        =   fields.Many2one('plm.document', 'name', ondelete='no action', readonly=True, help=_('This is the document object that declares this BoM.'))
    type             =   fields.Selection([('normal', _('Normal BoM')), ('phantom', _('Sets / Phantom')), ('ebom', _('Engineering BoM')), ('spbom', _('Spare BoM'))], _('BoM Type'), required=True, help = 
                    _("Phantom BOM: When processing a sales order for this product, the delivery order will contain the raw materials, instead of the finished product." \
        " Ship this product as a set of components (kit)."))
    weight_net      =   fields.Float('Weight', digits_compute=dp.get_precision(_('Stock Weight')), help=_("The BoM net weight in Kg."))
    ebom_source_id  = fields.Integer('Source Ebom ID')


    _defaults = {
        'product_uom': 1,
        'weight_net': 0.0,
    }

    def init(self, cr):
        self._packed = []

    def _getinbom(self, cr, uid, pid, sid=False):
        bomLType = self.pool.get('mrp.bom.line')
        ids = []
        if sid:
            ids = bomLType.search(cr, uid, [('product_id', '=', pid),
                                            ('source_id', '=', sid),
                                            ('type', '=', 'ebom')])
            if not ids:
                ids = bomLType.search(cr, uid, [('product_id', '=', pid),
                                                ('source_id', '=', sid),
                                                ('type', '=', 'normal')])
        else:
            ids = bomLType.search(cr, uid, [('product_id', '=', pid),
                                            ('source_id', '=', False),
                                            ('type', '=', 'ebom')])
            if not ids:
                ids = bomLType.search(cr, uid, [('product_id', '=', pid),
                                                ('source_id', '=', False),
                                                ('type', '=', 'normal')])
        if not ids:
            ids = bomLType.search(cr, uid, [('product_id', '=', pid),
                                            ('type', '=', 'ebom')])
            if not ids:
                ids = bomLType.search(cr, uid, [('product_id', '=', pid),
                                                ('type', '=', 'normal')])
        return bomLType.browse(cr, uid, list(set(ids)), context=None)

    def _getbom(self, cr, uid, pid, sid=False):
        if sid is None:
            sid = False
        ids = self.search(cr, uid, [('product_tmpl_id', '=', pid), ('source_id', '=', sid), ('type', '=', 'ebom')])
        if not ids:
            ids = self.search(cr, uid, [('product_tmpl_id', '=', pid), ('source_id', '=', sid), ('type', '=', 'normal')])
            if not ids:
                ids = self.search(cr, uid, [('product_tmpl_id', '=', pid), ('source_id', '=', False), ('type', '=', 'ebom')])
                if not ids:
                    ids = self.search(cr, uid, [('product_tmpl_id', '=', pid), ('source_id', '=', False), ('type', '=', 'normal')])
                    if not ids:
                        ids = self.search(cr, uid, [('product_tmpl_id', '=', pid), ('type', '=', 'ebom')])
                        if not ids:
                            ids = self.search(cr, uid, [('product_tmpl_id', '=', pid), ('type', '=', 'normal')])
        return self.browse(cr, uid, list(set(ids)), context=None)

    def getListIdsFromStructure(self, structure):
        '''
            Convert from [id1,[[id2,[]]]] to [id1,id2]
        '''
        outList = []
        if isinstance(structure, (list, tuple)) and len(structure) == 2:
            outList.append(structure[0])
            for item in structure[1]:
                outList.extend(self.getListIdsFromStructure(item))
        return list(set(outList))

    def _getpackdatas(self, cr, uid, relDatas):
        prtDatas = {}
        tmpids = self.getListIdsFromStructure(relDatas)
        if not tmpids or len(tmpids) < 1:
            return prtDatas
        compType = self.pool.get('product.product')
        tmpDatas = compType.read(cr, uid, tmpids)
        for tmpData in tmpDatas: 
            for keyData in tmpData.keys():
                if tmpData[keyData] is None:
                    del tmpData[keyData]
            prtDatas[str(tmpData['id'])] = tmpData
        return prtDatas

    def _getpackreldatas(self, cr, uid, relDatas, prtDatas):
        relids = {}
        relationDatas = {}
        tmpids = self.getListIdsFromStructure(relDatas)
        if len(tmpids) < 1:
            return prtDatas
        for keyData in prtDatas.keys():
            tmpData = prtDatas[keyData]
            if len(tmpData['bom_ids']) > 0:
                relids[keyData] = tmpData['bom_ids'][0]

        if len(relids) < 1:
            return relationDatas
        for keyData in relids.keys():
            relationDatas[keyData] = self.read(cr, uid, relids[keyData])
        return relationDatas

    def GetWhereUsed(self, cr, uid, ids, context=None):
        """
            Return a list of all fathers of a Part (all levels)
        """
        self._packed = []
        relDatas = []
        if len(ids) < 1:
            return None
        sid = False
        if len(ids) > 1:
            sid = ids[1]
        oid = ids[0]
        relDatas.append(oid)
        relDatas.append(self._implodebom(cr, uid, self._getinbom(cr, uid, oid, sid)))
        prtDatas = self._getpackdatas(cr, uid, relDatas)
        return (relDatas, prtDatas, self._getpackreldatas(cr, uid, relDatas, prtDatas))

    def GetExplose(self, cr, uid, ids, context=None):
        """
            Returns a list of all children in a Bom (all levels)
        """
        self._packed = []
        objId, _sourceID, lastRev = ids
        # get all ids of the children product in structured way like [[id,childids]]
        relDatas = [objId, self._explodebom(cr, uid, self._getbom(cr, uid, objId), False, lastRev)]
        prtDatas = self._getpackdatas(cr, uid, relDatas)
        return (relDatas, prtDatas, self._getpackreldatas(cr, uid, relDatas, prtDatas))

    def _explodebom(self, cr, uid, bids, check=True, lastRev=False):
        """
            Explodes a bom entity  ( check=False : all levels, check=True : one level )
        """
        output = []
        _packed = []
        for bid in bids:
            for bom_line in bid.bom_line_ids:
                if check and (bom_line.product_id.id in _packed):
                    continue
                tmpl_id = bom_line.product_id.product_tmpl_id.id
                prod_id = bom_line.product_id.id
                if lastRev:
                    newerCompId = self.getLastCompId(cr, uid, prod_id)
                    if newerCompId:
                        prod_id = newerCompId
                        newerCompBrws = self.pool.get('product.product').browse(cr, uid, newerCompId)
                        tmpl_id = newerCompBrws.product_tmpl_id.id
                innerids = self._explodebom(cr, uid, self._getbom(cr, uid, tmpl_id), check)
                _packed.append(prod_id)
                output.append([prod_id, innerids])
        return(output)

    def GetTmpltIdFromProductId(self, cr, uid, product_id=False):
        if not product_id:
            return False
        tmplDict = self.pool.get('product.product').read(cr, uid, product_id, ['product_tmpl_id'])  # tmplDict = {'product_tmpl_id': (tmpl_id, u'name'), 'id': product_product_id}
        tmplTuple = tmplDict.get('product_tmpl_id', {})
        if len(tmplTuple) == 2:
            return tmplTuple[0]
        return False

    def getLastCompId(self, cr, uid, compId):
        prodProdObj = self.pool.get('product.product')
        compBrws = prodProdObj.browse(cr, uid, compId)
        if compBrws:
            prodIds = prodProdObj.search(cr, uid, [('engineering_code', '=', compBrws.engineering_code)], order='engineering_revision DESC')
            if prodIds:
                return prodIds[0]
        return False

    def GetExploseSum(self, cr, uid, ids, context=None):
        """
            Return a list of all children in a Bom taken once (all levels)
        """
        compId, _source_id, latestFlag = ids
        self._packed    = []
        prodTmplId      = self.GetTmpltIdFromProductId(cr, uid, compId)
        bomId           = self._getbom(cr, uid, prodTmplId)
        explosedBomIds  = self._explodebom(cr, uid, bomId, True, latestFlag)
        relDatas        = [compId, explosedBomIds]
        prtDatas        = self._getpackdatas(cr, uid, relDatas)
        return (relDatas, prtDatas, self._getpackreldatas(cr, uid, relDatas, prtDatas))

    def _implodebom(self, cr, uid, bomObjs):
        """
            Execute implosion for a a bom object
        """
        pids = []
        for bomObj in bomObjs:
            if not bomObj.bom_id:
                continue
            if bomObj.bom_id.id in self._packed:
                continue
            self._packed.append(bomObj.bom_id.id)
            bomFthObj = self.browse(cr, uid, [bomObj.bom_id.id], context=None)
            if bomFthObj and bomFthObj.product_id.id:
                innerids = self._implodebom(cr, uid, self._getinbom(cr, uid, bomFthObj.product_id.id))
                pids.append((bomFthObj.product_id.id, innerids))
        return (pids)

    def GetWhereUsedSum(self, cr, uid, ids, context=None):
        """
            Return a list of all fathers of a Part (all levels)
        """
        self._packed = []
        relDatas = []
        if len(ids) < 1:
            return None
        sid = False
        if len(ids) > 1:
            sid = ids[1]
        oid = ids[0]
        relDatas.append(oid)
        bomId = self._getinbom(cr, uid, oid, sid)           # Get bom lines related to product.product (normal or ebom)
        relDatas.append(self._implodebom(cr, uid, bomId))   # Get [(idProd1, [(idProd2, [...])])] -->  products get from found bom
        prtDatas = self._getpackdatas(cr, uid, relDatas)    # Get {prodId: {prodVals}, ...} --> prodVals came from read
        return (relDatas, prtDatas, self._getpackreldatas(cr, uid, relDatas, prtDatas))

    def GetExplodedBom(self, cr, uid, ids, level=0, currlevel=0):
        """
            Return a list of all children in a Bom ( level = 0 one level only, level = 1 all levels)
        """
        self._packed = []
        result = []
        if level == 0 and currlevel > 1:
            return result
        bomids = self.browse(cr, uid, ids)
        for bomid in bomids:
            for bom in bomid.bom_line_ids:
                children = self.GetExplodedBom(cr, uid, [bom.id], level, currlevel + 1)
                result.extend(children)
            if len(str(bomid.bom_id)) > 0:
                result.append(bomid.id)
        return result

    def SaveStructure(self, cr, uid, relations, level=0, currlevel=0):
        """
            Save EBom relations
        """
        t_bom_line = self.pool.get('mrp.bom.line')
        t_product_product = self.pool.get('product.product')

        def cleanStructure(parentID=None, sourceID=None):
            """
                Clean relations having sourceID
            """
            if parentID is None or sourceID is None:
                return False
            objPart = t_product_product.browse(cr, uid, parentID, context=None)
            bomIds = self.search(cr, uid, ["|",
                                           ('product_id', '=', parentID),
                                           ('product_tmpl_id', '=', objPart.product_tmpl_id.id),
                                           ('source_id', '=', sourceID)])

            bomLineIds = t_bom_line.search(cr, uid, [('bom_id', 'in', bomIds),
                                                     ('source_id', '=', sourceID)])
            self.unlink(cr, uid, bomIds)
            t_bom_line.unlink(cr, uid, bomLineIds)
            return True

        def toCleanRelations(relations):
            """
                Processes relations
            """
            listedSource = []
            for _parentName, parentID, _ChildName, _ChildID, sourceID, _RelArgs in relations:
                if sourceID not in listedSource and cleanStructure(parentID, sourceID):
                    listedSource.append(sourceID)
            return False

        def toCompute(parentName, relations):
            """
                Processes relations
            """
            bomID = False
            nexRelation = []

            def divedeByParent(element):
                if element[0] == parentName:
                    return True
                nexRelation.append(element)
            subRelations = filter(divedeByParent, relations)
            if len(subRelations) < 1:  # no relation to save
                return
            parentName, parentID, _ChildName, _ChildID, sourceID, _RelArgs = subRelations[0]
            if not self.search(cr, uid, [('product_id', '=', parentID),
                                         ('source_id', '=', sourceID)]):
                bomID = saveParent(parentName, parentID, sourceID, kindBom='ebom')
                for parentName, parentID, childName, childID, sourceID, relArgs in subRelations:
                    if parentName == childName:
                        logging.error('toCompute : Father (%s) refers to himself' % (str(parentName)))
                        raise Exception(_('saveChild.toCompute : Father "%s" refers to himself' % (str(parentName))))

                    saveChild(childName, childID, sourceID, bomID, kindBom='ebom', args=relArgs)
                    toCompute(childName, nexRelation)
                self.RebaseProductWeight(cr, uid, bomID, self.RebaseBomWeight(cr, uid, bomID))
            return bomID

        def repairQty(value):
            if(not isinstance(value, float) or (value < 1e-6)):
                return 1.0
            return value

        def saveParent(name, partID, sourceID, kindBom=None, args=None):
            """
                Saves the relation ( parent side in mrp.bom )
            """
            try:
                res = {}
                if kindBom is not None:
                    res['type'] = kindBom
                else:
                    res['type'] = 'ebom'
                objPart = t_product_product.browse(cr, uid, partID, context=None)
                res['product_tmpl_id'] = objPart.product_tmpl_id.id
                res['product_id'] = partID
                res['source_id'] = sourceID
                #res['name'] = name
                if args is not None:
                    for arg in args:
                        res[str(arg)] = args[str(arg)]
                if ('product_qty' in res):
                    res['product_qty'] = repairQty(res['product_qty'])
                return self.create(cr, uid, res)
            except Exception, ex:
                logging.error("saveParent :  unable to create a relation for part (%s) with source (%d) : %s. %r" % (name, sourceID, str(args), ex))
                raise AttributeError(_("saveParent :  unable to create a relation for part (%s) with source (%d) : %s." %(name,sourceID,str(sys.exc_info()))))

        def saveChild(name, partID, sourceID, bomID=None, kindBom=None, args=None):
            """
                Saves the relation ( child side in mrp.bom.line )
            """
            try:
                res = {}
                if bomID is not None:
                    res['bom_id'] = bomID
                if kindBom is not None:
                    res['type'] = kindBom
                else:
                    res['type'] = 'ebom'
                res['product_id'] = partID
                res['source_id'] = sourceID
                #res['name'] = name
                if args is not None:
                    for arg in args:
                        res[str(arg)] = args[str(arg)]
                if ('product_qty' in res):
                    res['product_qty'] = repairQty(res['product_qty'])
                return t_bom_line.create(cr, uid, res)
            except:
                logging.error("saveChild :  unable to create a relation for part (%s) with source (%d) : %s." % (name, sourceID, str(args)))
                raise AttributeError(_("saveChild :  unable to create a relation for part (%s) with source (%d) : %s." % (name, sourceID, str(sys.exc_info()))))

        if len(relations) < 1:  # no relation to save
            return False
        parentName, _parentID, _childName, _childID, _sourceID, _relArgs = relations[0]
        toCleanRelations(relations)
        toCompute(parentName, relations)
        return False

    def _sumBomWeight(self, bomObj):
        """
            Evaluates net weight for assembly, based on BoM object
        """
        weight=0.0
        for bom_line in bomObj.bom_line_ids:
            weight+=(bom_line.product_qty * bom_line.product_id.product_tmpl_id.weight)
        return weight

    def RebaseProductWeight(self, cr, uid, parentBomID, weight=0.0):
        """
            Evaluates net weight for assembly, based on product ID
        """
        if not(parentBomID==None) or parentBomID:
            bomObj=self.browse(cr,uid,parentBomID,context=None)
            self.pool.get('product.product').write(cr,uid,[bomObj.product_id.id],{'weight': weight})
            
    def RebaseBomWeight(self, cr, uid, bomID, context=None):
        """
            Evaluates net weight for assembly, based on BoM ID
        """
        weight=0.0
        if  bomID:
            for bomId in self.browse(cr, uid, bomID, context):
                weight=self._sumBomWeight(bomId)
                super(plm_relation,self).write(cr, uid, [bomId.id], {'weight_net': weight}, context=context)
        return weight


#   Overridden methods for this entity
    def write(self, cr, uid, ids, vals, check=True, context=None):
        ret = super(plm_relation, self).write(cr, uid, ids, vals, context=context)
        for bomId in self.browse(cr, uid, ids, context=None):
            self.RebaseBomWeight(cr, uid, bomId.id, context=context)
        return ret

    def copy(self, cr, uid, oid, defaults={}, context=None):
        """
            Return new object copied (removing SourceID)
        """
        newId = super(plm_relation, self).copy(cr, uid, oid, defaults, context=context)
        if newId:
            compType = self.pool.get('product.product')
            bomLType = self.pool.get('mrp.bom.line')
            newOid = self.browse(cr, uid, newId, context=context)
            for bom_line in newOid.bom_line_ids:
                lateRevIdC = compType.GetLatestIds(cr, uid, [(bom_line.product_id.product_tmpl_id.engineering_code, False, False)], context=context)  # Get Latest revision of each Part
                bomLType.write(cr, uid, [bom_line.id], {'source_id': False, 'name': bom_line.product_id.product_tmpl_id.name, 'product_id': lateRevIdC[0]}, context=context)
            self.write(cr, uid, [newId], {'source_id': False, 'name': newOid.product_tmpl_id.name}, check=False, context=context)
        return newId

#   Overridden methods for this entity
    @api.one
    def deleteChildRow(self, documentId):
        """
        delete the bom child row
        """
        for bomLine in self.bom_line_ids:
            if bomLine.source_id.id == documentId and bomLine.type == self.type:
                bomLine.unlink()

    @api.model
    def addChildRow(self, childId, sourceDocumentId, relationAttributes):
        """
        add children rows
        """
        relationAttributes.update({'bom_id': self.id,
                                   'product_id': childId,
                                   'source_id': sourceDocumentId,
                                   'type': 'ebom'})
        self.bom_line_ids.ids.append(self.env['mrp.bom.line'].create(relationAttributes).id)

plm_relation()


class plm_material(models.Model):
    _name = "plm.material"
    _description = "PLM Materials"

    name            =   fields.Char(_('Designation'), size=128, required=True)
    description     =   fields.Char(_('Description'), size=128)
    sequence        =   fields.Integer(_('Sequence'), help=_("Gives the sequence order when displaying a list of product categories."))

#    _defaults = {
#        'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'plm.material'),
#    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', _('Raw Material has to be unique !')),
    ]
plm_material()


class plm_finishing(models.Model):
    _name = "plm.finishing"
    _description = "Surface Finishing"

    name            =   fields.Char(_('Specification'), size=128, required=True)
    description     =   fields.Char(_('Description'), size=128)
    sequence        =   fields.Integer(_('Sequence'), help=_("Gives the sequence order when displaying a list of product categories."))

#    _defaults = {
#        'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'plm.finishing'),
#    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', _('Raw Material has to be unique !')),
    ]
plm_finishing()


class plm_temporary(osv.osv.osv_memory):
    _name = "plm.temporary"
    _description = "Temporary Class"
    name = fields.Char(_('Temp'), size=128)
    summarize = fields.Boolean('Summarize Bom Lines if needed.', help="If set as true, when a Bom line comes from EBOM was in the old normal BOM two lines where been summarized.")

    def action_create_normalBom(self, cr, uid, ids, context=None):
        """
            Create a new Normal Bom if doesn't exist (action callable from views)
        """
        summarize = self.browse(cr, uid, ids[0], context).summarize
        selectdIds = context.get('active_ids', [])
        objType = context.get('active_model', '')
        if objType != 'product.product':
            raise UserError(_("The creation of the normalBom works only on product_product object"))
        if not selectdIds:
            raise UserError(_("Select a product before to continue"))
        objType = context.get('active_model', False)
        product_product_type_object = self.pool.get(objType)
        for productBrowse in product_product_type_object.browse(cr, uid, selectdIds, context):
            idTemplate = productBrowse.product_tmpl_id.id
            objBoms = self.pool.get('mrp.bom').search(cr, uid, [('product_tmpl_id', '=', idTemplate),
                                                                ('type', '=', 'normal')])
            if objBoms:
                raise UserError(_("Normal BoM for Part %r already exists." % (objBoms)))
            lineMessaggesList = product_product_type_object.create_bom_from_ebom(cr, uid, productBrowse, 'normal', summarize, context)
            if lineMessaggesList:
                outMess = ''
                for mess in lineMessaggesList:
                    outMess = outMess + '\n' + mess
                t_mess_obj = self.pool.get("plm.temporary.message")
                t_mess_id = t_mess_obj.create(cr, uid, {'name': outMess})
                return {'name': _('Result'),
                        'view_type': 'form',
                        "view_mode": 'form',
                        'res_model': "plm.temporary.message",
                        'res_id': t_mess_id,
                        'type': 'ir.actions.act_window',
                        'target': 'new',
                        }
        return {}
plm_temporary()


class plm_temporary_message(osv.osv.osv_memory):
    _name = "plm.temporary.message"
    _description = "Temporary Class"
    name = fields.Text(_('Bom Result'), readonly=True)

plm_temporary_message()
