# Part of Odoo. See LICENSE file for full copyright and licensing details.
# -*- coding: utf-8 -*-
from lxml import etree

import odoo.tests
from odoo import Command


@odoo.tests.tagged('post_install', '-at_install')
class TestUi(odoo.tests.HttpCase):

    def test_new_app_and_report(self):
        self.start_tour("/web", 'web_studio_new_app_tour', login="admin")

        # the report tour is based on the result of the former tour
        self.start_tour("/web?debug=tests", 'web_studio_new_report_tour', login="admin")
        self.start_tour("/web?debug=tests", "web_studio_new_report_basic_layout_tour", login="admin")

    def test_optional_fields(self):
        self.start_tour("/web?debug=tests", 'web_studio_hide_fields_tour', login="admin")

    def test_model_option_value(self):
        self.start_tour("/web?debug=tests", 'web_studio_model_option_value_tour', login="admin")

    def test_rename(self):
        self.start_tour("/web?debug=tests", 'web_studio_tests_tour', login="admin", timeout=200)

    def test_approval(self):
        self.start_tour("/web?debug=tests", 'web_studio_approval_tour', login="admin")

    def test_background(self):
        attachment = self.env['ir.attachment'].create({
            'datas': b'R0lGODdhAQABAIAAAP///////ywAAAAAAQABAAACAkQBADs=',
            'name': 'testFilename.gif',
            'public': True,
            'mimetype': 'image/gif'
        })
        self.env.company.background_image = attachment.datas
        self.start_tour("/web?debug=tests", 'web_studio_custom_background_tour', login="admin")

    def test_alter_field_existing_in_multiple_views(self):
        created_model_name = None
        studio_model_create = type(self.env["ir.model"]).studio_model_create
        def mock_studio_model_create(*args, **kwargs):
            nonlocal created_model_name
            res = studio_model_create(*args, **kwargs)
            created_model_name = res[0].model
            return res

        self.patch(type(self.env["ir.model"]), "studio_model_create", mock_studio_model_create)
        self.start_tour("/web?debug=tests", 'web_studio_alter_field_existing_in_multiple_views_tour', login="admin")

        # we can't assert xml equality as a lot of stuff in the arch are set randomly
        view = self.env["ir.ui.view"].search([("model", "=", created_model_name), ("type", "=", "form")], limit=1)
        tree = etree.fromstring(view.get_combined_arch())
        root = tree.getroottree()

        fields_of_interest = tree.xpath("//field[@name='message_partner_ids']")
        self.assertEqual(len(fields_of_interest), 2)

        # First field is on the main model: not below another field
        # The second one is in a subview
        self.assertEqual(root.getpath(fields_of_interest[0]), "/form/sheet/group/group[1]/field")
        self.assertEqual(root.getpath(fields_of_interest[1]), "/form/sheet/field[2]/tree/field[1]")

        # The tour in its final steps is putting invisible on the field in the subview
        self.assertEqual(fields_of_interest[0].get("invisible"), None)
        self.assertEqual(fields_of_interest[1].get("invisible"), "1")

@odoo.tests.tagged('post_install', '-at_install')
class TestStudioUIUnit(odoo.tests.HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.testView = cls.env["ir.ui.view"].create({
            "name": "simple partner",
            "model": "res.partner",
            "type": "form",
            "arch": '''
                <form>
                    <group>
                        <field name="name" />
                    </group>
                </form>
            '''
        })
        cls.testAction = cls.env["ir.actions.act_window"].create({
            "name": "simple partner",
            "res_model": "res.partner",
            "view_ids": [Command.create({"view_id": cls.testView.id, "view_mode": "form"})]
        })
        cls.testActionXmlId = cls.env["ir.model.data"].create({
            "name": "studio_test_partner_action",
            "model": "ir.actions.act_window",
            "module": "web_studio",
            "res_id": cls.testAction.id,
        })
        cls.testMenu = cls.env["ir.ui.menu"].create({
            "name": "Studio Test Partner",
            "action": "ir.actions.act_window,%s" % cls.testAction.id
        })
        cls.testMenuXmlId = cls.env["ir.model.data"].create({
            "name": "studio_test_partner_menu",
            "model": "ir.ui.menu",
            "module": "web_studio",
            "res_id": cls.testMenu.id,
        })

    def test_create_one2many_lines_then_edit_name(self):
        custom_fields_before_studio = self.env["ir.model.fields"].search([
            ("state", "=", "manual"),
        ])

        self.start_tour("/web?debug=tests", 'web_studio_test_create_one2many_lines_then_edit_name', login="admin", timeout=30000)

        custom_fields = self.env["ir.model.fields"].search_read([
            ("state", "=", "manual"),
            ("id", "not in", custom_fields_before_studio.ids),
        ], fields=["name", "ttype", "field_description"])

        self.maxDiff = None
        self.assertCountEqual(
            [{key: val for key, val in field.items() if key != 'id'} for field in custom_fields],
            [
                {"name": "x_studio_new_name", 'ttype': 'one2many', 'field_description': 'new name'},
                {"name": "x_name", 'ttype': 'char', 'field_description': 'Description'},
                {"name": "x_res_partner_id", 'ttype': 'many2one', 'field_description': 'X Res Partner'},
                {"name": "x_studio_sequence", 'ttype': 'integer', 'field_description': 'Sequence'},
            ]
        )

    def test_address_view_id_no_edit(self):
        self.testView.write({
            "arch": '''
                <form>
                    <div class="o_address_format">
                        <field name="lang"/>
                    </div>
                </form>
            '''
        })

        self.env.company.country_id.address_view_id = self.env.ref('base.view_partner_address_form')
        self.start_tour("/web?debug=tests", 'web_studio_test_address_view_id_no_edit', login="admin", timeout=200)
