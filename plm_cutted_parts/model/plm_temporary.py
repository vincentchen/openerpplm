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
from openerp import api
from openerp import _
from openerp.tools.float_utils import float_round
_logger = logging.getLogger(__name__)


class plm_temporary_cutted(models.Model):
    _inherit = 'plm.temporary'
    cutted_part_explosion = fields.Selection([('none', 'None'),
                                              ('explode', 'Explode'),
                                              ('replace', 'Replace')],
                                             'Cutted Part Action',
                                             default='none')

    @api.multi
    def action_create_normalBom(self):
        selectdIds = self.env.context.get('active_ids', [])
        objType = self.env.context.get('active_model', '')
        responce = super(plm_temporary_cutted, self).action_create_normalBom()
        explosion_action = self.cutted_part_explosion
        if explosion_action != 'none':
            product_product_type_object = self.env[objType]
            mrp_bom_type_object = self.env['mrp.bom']
            mrp_bom_line_type_object = self.env['mrp.bom.line']

            def computeProductEfficiency(xMaterial, yMaterial, xRawMaterialLenght, yRawMaterialLenght):
                if xRawMaterialLenght <= 1 and yRawMaterialLenght > 1: # No X dimension available
                    return int(yRawMaterialLenght / yMaterial) / (yRawMaterialLenght / yMaterial)
                elif yRawMaterialLenght <= 1 and xRawMaterialLenght > 1: # No Y dimension available
                    return int(xRawMaterialLenght / xMaterial) / (xRawMaterialLenght / xMaterial)
                elif yRawMaterialLenght > 1 and xRawMaterialLenght > 1:   # 2 dimensional product
                    yEfficiency = int(yRawMaterialLenght / yMaterial) / (yRawMaterialLenght / yMaterial)
                    xEfficiency = int(xRawMaterialLenght / xMaterial) / (xRawMaterialLenght / xMaterial)
                    return (yEfficiency + xEfficiency) / 2
                return 1    # No dimension in X and in Y
            
            def cuttedPartAction(bomLine):
                prodBrws = bomLine.product_id
                prodRaw = prodBrws.row_material
                materiaPercentage = (1 + prodBrws.wastage_percent)
                xMaterial = (prodBrws.row_material_xlenght * materiaPercentage) + prodBrws.material_added
                yMaterial = (prodBrws.row_material_ylenght * materiaPercentage) + prodBrws.material_added_y
                xRawMaterialLenght = prodRaw.row_material_xlenght
                xRawMaterialLenght = 1 if xRawMaterialLenght == 0 else xRawMaterialLenght
                yRawMaterialLenght = prodRaw.row_material_ylenght
                yRawMaterialLenght = 1 if yRawMaterialLenght == 0 else yRawMaterialLenght
                xQty = xMaterial / (xRawMaterialLenght)
                yQty = yMaterial / (yRawMaterialLenght)
                qty = xQty * yQty
                
                product_efficiency = float_round(computeProductEfficiency(xMaterial, yMaterial, xRawMaterialLenght, yRawMaterialLenght),
                                                 precision_digits=self.env['decimal.precision'].precision_get('plm_cutted_parts'))
                commonValues = {'x_leght': xMaterial,
                                'y_leght': yMaterial,
                                'product_qty': 1 if qty == 0 else qty,  # set to 1 because odoo dose not manage qty==0
                                'product_id': prodRaw.id,
                                'product_rounding': prodBrws.bom_rounding,
                                'product_efficiency': product_efficiency
                                }
                if explosion_action == 'replace':
                    commonValues['product_qty'] = bomLine.product_qty * commonValues['product_qty']
                    bomLine.write(commonValues)
                else:
                    idTemplate = prodBrws.product_tmpl_id.id
                    bomBrwsList = mrp_bom_type_object.search([('product_tmpl_id', '=', idTemplate),
                                                                  ('type', '=', 'normal')])

                    if not bomBrwsList:
                        values = {'product_tmpl_id': idTemplate,
                                  'type': 'normal'}
                        newBomId = mrp_bom_type_object.create(values)
                        values = {'type': 'normal',
                                  'bom_id': newBomId}
                        values.update(commonValues)
                        mrp_bom_line_type_object.create(values)
                    else:
                        for bomId in bomBrwsList:
                            if len(bomId.bom_line_ids) > 1:
                                raise osv.osv.except_osv(_('Bom Generation Error'), 'Bom "%s" has more than one line, please check better.' % (bomId.product_tmpl_id.engineering_code))
                            for bomLineId in bomId.bom_line_ids:
                                logging.info("Bom line updated %r" % bomLineId)
                                bomLineId.write(commonValues)
                                return

            def actionOnBom(productIds):
                for productBrowse in product_product_type_object.browse(productIds):
                    idTemplate = productBrowse.product_tmpl_id.id
                    bomBrwsList = mrp_bom_type_object.search([('product_tmpl_id', '=', idTemplate),
                                                                  ('type', '=', 'normal')])
                    for bomObj in bomBrwsList:
                        for bom_line in bomObj.bom_line_ids:
                            if bom_line.product_id.row_material:
                                cuttedPartAction(bom_line)
                            else:
                                actionOnBom([bom_line.product_id.id])
            actionOnBom(selectdIds)
        return responce

plm_temporary_cutted()
