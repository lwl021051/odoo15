# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _

class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model
    def balance_sheet_menu_item_clicked(self):
        current_company = self.env.company

        spanish_coa_bs_map = {
            self.env.ref('l10n_es.account_chart_template_pymes'): self.env.ref("l10n_es_reports.financial_report_balance_sheet_pymes").id,
            self.env.ref('l10n_es.account_chart_template_full'): self.env.ref("l10n_es_reports.financial_report_balance_sheet_full").id,
            self.env.ref('l10n_es.account_chart_template_assoc'): self.env.ref("l10n_es_reports.financial_report_balance_sheet_assoc").id,
        }
        default_bs = self.env.ref('account_reports.account_financial_report_balancesheet0').id

        return {
                'name': _('Balance Sheet'),
                'type': 'ir.actions.client',
                'tag': 'account_report',
                'context': {
                    'model': 'account.financial.html.report',
                    'id': spanish_coa_bs_map.get(current_company.chart_template_id, default_bs),
                }
            }

    @api.model
    def open_aeat_tax_report(self, modelo):
        report_wizard = self.env['l10n_es_reports.mod' + modelo + '.wizard'].create({})

        return {
                'name': _('AEAT Tax Report'),
                'view_mode': 'form',
                'view_id': self.env.ref('l10n_es_reports.mod' + modelo + '_report_wizard').id,
                'res_model': 'l10n_es_reports.mod' + modelo + '.wizard',
                'type': 'ir.actions.act_window',
                'res_id': report_wizard.id,
                'target': 'new'
            }

    def _get_mod_boe_sequence(self, mod_version):
        """ Get or create mod BOE sequence for the current company

        :param str mod_version: any of "347" or "349"
        :return: the sequence record
        """
        self.ensure_one()
        assert mod_version in ("347", "349")
        mod_sequence_code = 'l10n_es.boe.mod_%s' % mod_version
        mod_sequence = self.env['ir.sequence'].search([
            ('company_id', '=', self.id), ('code', '=', mod_sequence_code),
        ])
        if not mod_sequence:
            mod_sequence = self.env["ir.sequence"].create({
                'name': "Mod %s BOE sequence for company %s" % (mod_version, self.name),
                'code': mod_sequence_code,
                'padding': 10,
                'company_id': self.id,
            })
        return mod_sequence[0]
