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
from openerp import models
from openerp import fields
from openerp import osv
from openerp import _
_logger = logging.getLogger(__name__)


class plm_temporary_cutted(models.Model):
    _inherit = 'plm.temporary'
    cutted_part_explosion = fields.Selection([('none', 'None'),
                                              ('explode', 'Explode'),
                                              ('replace', 'Replace')],
                                             'Cutted Part Action',
                                             default='none')

    def action_create_normalBom(self, cr, uid, ids, context={}):
        selectdIds = context.get('active_ids', [])
        objType = context.get('active_model', '')
        responce = super(plm_temporary_cutted, self).action_create_normalBom(cr,
                                                                             uid,
                                                                             ids,
                                                                             context)
        explosion_action = self.browse(cr, uid, ids[0], context).cutted_part_explosion
        if explosion_action != 'none':
            product_product_type_object = self.pool.get(objType)
            mrp_bom_type_object = self.pool.get('mrp.bom')
            mrp_bom_line_type_object = self.pool.get('mrp.bom.line')

            def cuttedPartAction(bomLine):
                materiaPercentage = (1 + bomLine.product_id.wastage_percent)
                xMaterial = (bomLine.product_id.row_material_xlenght * materiaPercentage) + bomLine.product_id.material_added
                yMaterial = (bomLine.product_id.row_material_ylenght * materiaPercentage) + bomLine.product_id.material_added
                xRawMaterialLenght = bomLine.product_id.row_material.row_material_xlenght
                yRawMaterialLenght = bomLine.product_id.row_material.row_material_ylenght
                xQty = xMaterial / (1 if xRawMaterialLenght == 0 else xRawMaterialLenght)
                yQty = yMaterial / (1 if yRawMaterialLenght == 0 else yRawMaterialLenght)
                qty = xQty * yQty
                commonValues = {'x_leght': xMaterial,
                                'y_leght': yMaterial,
                                'product_qty': 1 if qty == 0 else qty,  # set to 1 because odoo dose not manage qty==0
                                'product_id': bomLine.product_id.row_material.id,
                                'product_rounding': bomLine.product_id.bom_rounding}
                if explosion_action == 'replace':
                    commonValues['product_qty'] = bomLine.product_qty * commonValues['product_qty']
                    mrp_bom_line_type_object.write(cr, uid, [bomLine.id], commonValues)
                else:
                    idTemplate = bomLine.product_id.product_tmpl_id.id
                    bomIds = mrp_bom_type_object.search(cr, uid, [('product_tmpl_id', '=', idTemplate),
                                                                  ('type', '=', 'normal')])

                    if not bomIds:
                        values = {'product_tmpl_id': idTemplate,
                                  'type': 'normal'}
                        newBomId = mrp_bom_type_object.create(cr, uid, values)
                        values = {'type': 'normal',
                                  'bom_id': newBomId}
                        values.update(commonValues)
                        mrp_bom_line_type_object.create(cr, uid, values)
                    else:
                        for bomId in mrp_bom_type_object.browse(cr, uid, bomIds):
                            if len(bomId.bom_line_ids) > 1:
                                raise osv.osv.except_osv(_('Bom Generation Error'), 'Bom "%s" has more than one line, please check better.' % (bomId.product_tmpl_id.engineering_code))
                            for bomLineId in bomId.bom_line_ids:
                                logging.info("Bom line updated %r" % bomLineId)
                                mrp_bom_line_type_object.write(cr, uid, [bomLineId.id], commonValues)
                                return
                        logging.warning("No Bom Line detected for bom %r" % bomIds.id)

            def actionOnBom(productIds):
                for productBrowse in product_product_type_object.browse(cr, uid, productIds, context):
                    idTemplate = productBrowse.product_tmpl_id.id
                    bomIds = mrp_bom_type_object.search(cr, uid, [('product_tmpl_id', '=', idTemplate),
                                                                  ('type', '=', 'normal')])
                    for bomObj in mrp_bom_type_object.browse(cr, uid, bomIds, context):
                        for bom_line in bomObj.bom_line_ids:
                            if bom_line.product_id.row_material:
                                cuttedPartAction(bom_line)
                            else:
                                actionOnBom([bom_line.product_id.id])
            actionOnBom(selectdIds)
        return responce

plm_temporary_cutted()
