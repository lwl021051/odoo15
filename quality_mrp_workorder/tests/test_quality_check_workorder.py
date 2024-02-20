# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import Form
from odoo.addons.mrp.tests.common import TestMrpCommon


class TestQualityCheckWorkorder(TestMrpCommon):

    def test_01_quality_check_with_component_consumed_in_operation(self):
        """ Test quality check on a production with a component consumed in one operation
        """

        picking_type_id = self.env.ref('stock.warehouse0').manu_type_id.id
        component = self.env['product.product'].create({
            'name': 'consumable component',
            'type': 'consu',
        })
        bom = self.bom_2.copy()
        bom.bom_line_ids[0].product_id = component

        # Registering the first component in the operation of the BoM
        bom.bom_line_ids[0].operation_id = bom.operation_ids[0]

        # Create Quality Point for the product consumed in the operation of the BoM
        self.env['quality.point'].create({
            'product_ids': [bom.bom_line_ids[0].product_id.id],
            'picking_type_ids': [picking_type_id],
            'measure_on': 'product',
        })
        # Create Quality Point for all products (that should not apply on components)
        self.env['quality.point'].create({
            'product_ids': [],
            'picking_type_ids': [picking_type_id],
            'measure_on': 'product',
        })

        # Create Production of Painted Boat to produce 5.0 Unit.
        production_form = Form(self.env['mrp.production'])
        production_form.product_id = bom.product_id
        production_form.bom_id = bom
        production_form.product_qty = 5.0
        production = production_form.save()
        production.action_confirm()
        production.qty_producing = 3.0

        # Check that the Quality Check were created and has correct values
        self.assertEqual(len(production.move_raw_ids[0].move_line_ids.check_ids), 2)
        self.assertEqual(len(production.move_raw_ids[1].move_line_ids.check_ids), 0)
        self.assertEqual(len(production.check_ids.filtered(lambda qc: qc.product_id == production.product_id)), 1)
        self.assertEqual(len(production.check_ids), 2)

        # Registering consumption in tablet view
        wo = production.workorder_ids[0]
        wo.open_tablet_view()
        wo.qty_done = 10.0
        wo.action_next()
        self.assertEqual(len(production.move_raw_ids[0].move_line_ids.check_ids), 2)

    def test_register_consumed_materials(self):
        """
        Process a MO based on a BoM with one operation. That operation has one
        step: register the used component. Both finished product and component
        are tracked by serial. The auto-completion of the serial numbers should
        be correct
        """
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)

        finished = self.bom_4.product_id
        component = self.bom_4.bom_line_ids.product_id
        (finished | component).write({
            'type': 'product',
            'tracking': 'serial',
        })

        finished_sn, component_sn = self.env['stock.production.lot'].create([{
            'name': p.name,
            'product_id': p.id,
            'company_id': self.env.company.id,
        } for p in (finished, component)])
        self.env['stock.quant']._update_available_quantity(component, warehouse.lot_stock_id, 1, lot_id=component_sn)

        type_register_materials = self.env.ref('mrp_workorder.test_type_register_consumed_materials')
        operation = self.env['mrp.routing.workcenter'].create({
            'name': 'Super Operation',
            'bom_id': self.bom_4.id,
            'workcenter_id': self.workcenter_2.id,
            'quality_point_ids': [(0, 0, {
                'product_ids': [(4, finished.id)],
                'picking_type_ids': [(4, warehouse.manu_type_id.id)],
                'test_type_id': type_register_materials.id,
                'component_id': component.id,
                'bom_id': self.bom_4.id,
                'measure_on': 'operation',
            })]
        })
        self.bom_4.operation_ids = [(6, 0, operation.ids)]

        mo_form = Form(self.env['mrp.production'])
        mo_form.bom_id = self.bom_4
        mo = mo_form.save()
        mo.action_confirm()

        mo_form = Form(mo)
        mo_form.lot_producing_id = finished_sn
        mo = mo_form.save()

        self.assertEqual(mo.workorder_ids.finished_lot_id, finished_sn)
        self.assertEqual(mo.workorder_ids.lot_id, component_sn)

        mo.workorder_ids.action_next()
        mo.workorder_ids.do_finish()
        mo.button_mark_done()

        self.assertRecordValues(mo.move_raw_ids.move_line_ids + mo.move_finished_ids.move_line_ids, [
            {'qty_done': 1, 'lot_id': component_sn.id},
            {'qty_done': 1, 'lot_id': finished_sn.id},
        ])

    def test_control_per_op_quantity_quality_check(self):
        """ Test quality point control per product on workorder operation
        """
        self.env['quality.point'].create({
            'title': 'test QP1',
            'picking_type_ids': [(4, self.env['stock.picking.type'].search([('code', '=', 'mrp_operation')], limit=1).id)],
            'measure_on': 'product',
            'product_ids': [(4, self.bom_2.product_id.id, 0)],
            'operation_id': self.bom_2.operation_ids.id,
            'note': 'Cut',
        })

        mo_form = Form(self.env['mrp.production'])
        mo_form.bom_id = self.bom_2
        mo = mo_form.save()
        mo.action_confirm()

        # Check created on the workorder not the MO
        self.assertEqual(len(mo.check_ids), 0)
        self.assertEqual(len(mo.workorder_ids), 1)
        self.assertEqual(len(mo.workorder_ids.check_ids), 1)

    def test_register_consumed_materials_01(self):
        """
        Process a MO based on a BoM with one operation. That operation has one
        step: register the used component. Both finished product and component
        are tracked by serial. Changing both the finished product and the
        component serial at the same time should record both values.

        Also ensure if there is an overlapping quality.point for MOs (i.e. not
        a WO step), the SNs are as expected between:
        WO step <-> MO QC <-> move_line.lot_id
        regardless of which one is changed. All 3 use case occurring at the same
        time is unlikely, but helps tests expected behavior for the possible
        combinations of these use cases within 1 test
        """

        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)

        finished = self.bom_4.product_id
        component = self.bom_4.bom_line_ids.product_id
        (finished | component).write({
            'type': 'product',
            'tracking': 'serial',
        })

        finished_sn, component_sn = self.env['stock.production.lot'].create([{
            'name': p.name,
            'product_id': p.id,
            'company_id': self.env.company.id,
        } for p in (finished, component)])
        finished_sn2, component_sn2 = self.env['stock.production.lot'].create([{
            'name': p.name + "_2",
            'product_id': p.id,
            'company_id': self.env.company.id,
        } for p in (finished, component)])
        self.env['stock.quant']._update_available_quantity(component, warehouse.lot_stock_id, 1, lot_id=component_sn)
        self.env['stock.quant']._update_available_quantity(component, warehouse.lot_stock_id, 1, lot_id=component_sn2)

        type_register_materials = self.env.ref('mrp_workorder.test_type_register_consumed_materials')
        operation = self.env['mrp.routing.workcenter'].create({
            'name': 'Super Operation',
            'bom_id': self.bom_4.id,
            'workcenter_id': self.workcenter_2.id,
            'quality_point_ids': [(0, 0, {
                'product_ids': [(4, finished.id)],
                'picking_type_ids': [(4, warehouse.manu_type_id.id)],
                'test_type_id': type_register_materials.id,
                'component_id': component.id,
                'bom_id': self.bom_4,
                'measure_on': 'operation',
            })]
        })
        self.bom_4.operation_ids = [(6, 0, operation.ids)]

        self.env['quality.point'].create({
            'product_ids': [component.id],
            'picking_type_ids': [(4, warehouse.manu_type_id.id)],
            'measure_on': 'product',
        })

        mo_form = Form(self.env['mrp.production'])
        mo_form.bom_id = self.bom_4
        mo = mo_form.save()
        mo.action_confirm()

        self.assertEqual(mo.move_raw_ids.move_line_ids.lot_id, component_sn, "Unexpected reserved SN for MO component")
        self.assertEqual(mo.check_ids.lot_line_id, component_sn, "MO level QC should have been created with reserved SN")

        # test that production lot isn't used for comp lot
        mo_form = Form(mo)
        mo_form.lot_producing_id = finished_sn
        mo = mo_form.save()

        self.assertEqual(mo.workorder_ids.finished_lot_id, finished_sn)
        self.assertEqual(mo.workorder_ids.lot_id, component_sn, "WO level QC should still be using reserved SN")

        # test that changing both production lot + comp lot keeps the comp lot change
        wo = mo.workorder_ids[0]
        mo_form = Form(mo)
        mo_form.lot_producing_id = finished_sn2
        with Form(wo, view='mrp_workorder.mrp_workorder_view_form_tablet') as form:
            form.lot_id = component_sn2
        mo = mo_form.save()

        self.assertEqual(mo.workorder_ids.finished_lot_id, finished_sn2)
        self.assertEqual(mo.workorder_ids.lot_id, component_sn2, "WO level QC should be using newly selected SN")
        self.assertEqual(mo.check_ids.lot_line_id, component_sn, "MO level QC should still be using original reserved SN (WO step not validated)")
        self.assertEqual(mo.move_raw_ids.move_line_ids.lot_id, component_sn, "MO component SN should still be using original reserved SN (WO step not validated)")

        # change twice rather than make a 3rd SN to reproduce changing SN to something other than WO step SN
        mo.move_raw_ids.move_line_ids.lot_id = component_sn2
        self.assertEqual(mo.check_ids.lot_line_id, component_sn2, "MO level QC should update to match ml.lot_id")
        mo.move_raw_ids.move_line_ids.lot_id = component_sn
        self.assertEqual(mo.check_ids.lot_line_id, component_sn, "MO level QC should update to match ml.lot_id")
        self.assertEqual(mo.workorder_ids.lot_id, component_sn, "WO level QC should update to match ml.lot_id change")
        with Form(wo, view='mrp_workorder.mrp_workorder_view_form_tablet') as form:
            form.lot_id = component_sn2

        wo.action_next()
        wo.do_finish()

        self.assertEqual(mo.check_ids.lot_line_id, component_sn2, "MO level QC should update to match completed WO sn")
        self.assertEqual(mo.move_raw_ids.move_line_ids.lot_id, component_sn2, "MO component SN should update to match completed WO sn")
        mo.check_ids.do_pass()
        mo.button_mark_done()

        self.assertRecordValues(mo.move_raw_ids.move_line_ids + mo.move_finished_ids.move_line_ids, [
            {'qty_done': 1, 'lot_id': component_sn2.id},
            {'qty_done': 1, 'lot_id': finished_sn2.id},
        ])
