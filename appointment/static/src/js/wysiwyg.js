/** @odoo-module **/

import Wysiwyg from 'web_editor.wysiwyg'
import dialogs from 'web.view_dialogs'
import { preserveCursor } from '@web_editor/../lib/odoo-editor/src/OdooEditor';
import {_t} from 'web.core';

Wysiwyg.include({
    _getCommands: function () {
        const commands = this._super.apply(this, arguments);
        commands.push(...[
            {
                groupName: _t('Basic blocks'),
                title: _t('Appointment'),
                description: _t('Add a specific appointment.'),
                fontawesome: 'fa-calendar',
                callback: async () => {
                    const restoreSelection = preserveCursor(this.odooEditor.document);
                    const dialog = new dialogs.FormViewDialog(this, {
                        res_model: 'calendar.appointment.share',
                        res_id: 0,
                        res_ids: [],
                        res_IDs: [],
                        resIDs: [],
                        context: {
                            form_view_ref: "appointment.calendar_appointment_insert_share_view_form",
                            default_appointment_type_ids: [],
                            default_employee_ids: [],
                        },
                        title: _t("Insert Appointment Link"),
                        readonly: false,
                    });
                    dialog.open();
                    await dialog.opened();
                    const $dialog = $(dialog.el.closest('.modal-dialog'));
                    dialog.on('dialog_form_loaded', this, () => {
                        $dialog.find('.o_share_link_save').on('click', () => {
                            const url = $dialog.find('.o_appointement_share_link').text();
                            dialog.destroy();
                            const link = `<a href="${url}">Schedule an Appointment</a>`;
                            this.focus();
                            restoreSelection();
                            this.odooEditor.execCommand('insertHTML', link);
                        });
                        $dialog.find('.o_share_link_discard').on('click', () => {
                            dialog.destroy();
                        });
                    });
                },
            },
            {
                groupName: _t('Basic blocks'),
                title: _t('Calendar'),
                description: _t('Schedule an appointment.'),
                fontawesome: 'fa-calendar',
                callback: () => {
                    const link = `<a href="${window.location.origin}/calendar">Our Appointment Types</a>`;
                    this.odooEditor.execCommand('insertHTML', link);
                },
            },
        ]);
        return commands;
    }
});
