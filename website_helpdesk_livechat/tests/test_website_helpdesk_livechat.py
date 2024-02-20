# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from odoo import Command
from odoo.addons.helpdesk.tests.common import HelpdeskCommon


class TestWebsiteHelpdeskLivechat(HelpdeskCommon):

    def setUp(self):
        super().setUp()

        self.livechat_channel = self.env['im_livechat.channel'].create({
            'name': 'The channel',
            'user_ids': [Command.set([self.helpdesk_manager.id])]
        })

        self.patch(type(self.env['im_livechat.channel']), '_get_available_users', lambda _: self.helpdesk_manager)
        self.test_team.use_website_helpdesk_livechat = True


    def test_helpdesk_livechat_commands(self):
        public_user = self.env.ref('base.public_user')
        channel_info = self.livechat_channel.with_user(public_user)._open_livechat_mail_channel(anonymous_name='Visitor')
        mail_channel = self.env['mail.channel'].browse(channel_info['id']).with_user(self.helpdesk_manager)

        # Executes command /helpdesk
        mail_channel.execute_command_helpdesk(body="/helpdesk")

        bus = self.env['bus.bus'].search([('channel', 'like', f'"res.partner",{self.helpdesk_manager.partner_id.id}')], order='id desc', limit=1)
        message = json.loads(bus.message)

        self.assertIn("<b>@Public user</b>", message['payload']['body'], 'Command message should contains the username.')

        # chat with self
        private_channel = self.env['mail.channel'].with_user(self.helpdesk_manager).create({
            'name': 'Secret channel with self',
            'public': 'private',
            'channel_type': 'chat',
        })

        # Executes command /helpdesk
        private_channel.execute_command_helpdesk(body="/helpdesk")

        bus = self.env['bus.bus'].search([('channel', 'like', f'"res.partner",{self.helpdesk_manager.partner_id.id}')], order='id desc', limit=1)
        message = json.loads(bus.message)

        self.assertIn("<b>@Helpdesk Manager</b>.", message['payload']['body'], 'Command message should contains username.')
