# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import io

from odoo import api, fields, models, tools, _


class AccountGeneralLedger(models.AbstractModel):
    _inherit = 'account.general.ledger'

    def _get_reports_buttons(self, options):
        # OVERRIDE
        buttons = super()._get_reports_buttons(options)
        if self.env.company.account_fiscal_country_id.code == 'LT':
            buttons.append({'name': _('SAF-T'), 'sequence': 5, 'action': 'print_xml', 'file_export_type': _('XML')})
        return buttons

    @api.model
    def _prepare_saft_report_values(self, options):
        # OVERRIDE account_saft/models/account_general_ledger
        template_vals = super()._prepare_saft_report_values(options)

        if template_vals['company'].country_code != 'LT':
            return template_vals

        # The lithuanian version of the SAF-T requires account code to be provided along with the opening/closing
        # credit/debit of customers and suppliers
        accounts_by_partners = self._get_partners_accounts(options)

        for partner_vals in template_vals['customer_vals_list'] + template_vals['supplier_vals_list']:
            partner_id = partner_vals['partner'].id
            if partner_id in accounts_by_partners:
                partner_vals['accounts'] = list(accounts_by_partners[partner_id].values())

        # The owners also need account codes
        template_vals['owner_accounts'] = self._get_owner_accounts()

        template_vals.update({
            # Special LT SAF-T date format: YYYY-MM-DDThh:mm:ss
            'today_str': fields.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            'xmlns': 'https://www.vmi.lt/cms/saf-t',
            'file_version': '2.01',
            'accounting_basis': 'K',  # K (accrual - when recorded) or P (cash - when received)
            'entity': "COMPANY",
            'nb_of_parts': 1,
            'part_nb': 1,
        })
        return template_vals

    def _get_saft_report_account_type(self, account):
        # OVERRIDE account_saft/models/account_general_ledger
        if self.env.company.account_fiscal_country_id.code != 'LT':
            return super()._get_saft_report_account_type(account)

        # LT account types have to be identified as follows:
        # "IT" (Non-current assets), "TT" (Current assets), "NK" (Equity), "I" (Liabilities), "P" (Income), "S" (Costs), "KT" (Other)
        account_group_dict = {
            'asset': 'TT',
            'equity': 'NK',
            'liability': 'I',
            'income': 'P',
            'expense': 'S',
            'off_balance': 'KT',
        }
        if account.user_type_id in [self.env.ref('account.data_account_type_fixed_assets'),
                                    self.env.ref('account.data_account_type_non_current_assets')]:
            return 'IT'
        return account_group_dict[account.internal_group] or 'KT'

    def _get_saft_report_template(self):
        # OVERRIDE account_saft/models/account_general_ledger
        if self.env.company.account_fiscal_country_id.code != 'LT':
            return super()._get_saft_report_template()
        return self.env.ref('l10n_lt_saft.saft_template_inherit_l10n_lt_saft')

    def get_xml(self, options):
        # OVERRIDE account_saft/models/account_general_ledger
        content = super().get_xml(options)

        if self.env.company.account_fiscal_country_id.code != 'LT':
            return content

        xsd_attachment = self.env['ir.attachment'].search([('name', '=', 'xsd_cached_SAF-T_v2_01_20190306_xsd')])
        if xsd_attachment:
            with io.BytesIO(base64.b64decode(xsd_attachment.with_context(bin_size=False).datas)) as xsd:
                tools.xml_utils._check_with_xsd(content, xsd)
        return content

    def _get_owner_accounts(self):
        """Retrieve the account codes for every owners' account.
        Owners' account can be identified by their tag, i.e. account_account_tag_d_1_3

        :rtype: str
        :return: a string of the account codes, comma separated, for instance "303, 305, 308"
        """
        tag_id = self.env.ref('l10n_lt.account_account_tag_d_1_3').id
        owner_accounts = self.env["account.account"].search([('tag_ids', 'in', tag_id)])
        return ", ".join([account.code for account in owner_accounts])

    def _get_partners_accounts(self, options):
        """Retrieve the accounts used for transactions with the different partners (customer/supplier).

        The Lithuanian regulation (based on xsd file) requires a list of accounts for every partner, with starting and closing balances.
        The partner ledger in Odoo provides starting and closing balance for every partner, but it is account insensitive.
        So it is needed to fetch account lines in order to compute all of this, on account/partner basis.

        :rtype: dict
        :return: dictionary of partners' accounts with the account code and its opening/closing balance
        """
        date_from = fields.Date.to_date(options['date']['date_from'])
        date_to = fields.Date.to_date(options['date']['date_to'])
        modified_options = options.copy()
        # Fetch data from beginning
        modified_options['date']['date_from'] = False
        tables, where_clause, where_params = self._query_get(modified_options)
        # The balance dating from earlier periods are computed as opening
        # The balance up to the end of the current period are computed as closing
        self._cr.execute(f'''
            SELECT DISTINCT
                account_move_line.partner_id,
                account.code,
                CASE WHEN account_move_line.date < '{date_from}' THEN SUM(account_move_line.balance) ELSE 0 END AS opening_balance,
                CASE WHEN account_move_line.date <= '{date_to}'  THEN SUM(account_move_line.balance) ELSE 0 END AS closing_balance
            FROM {tables}
            JOIN account_account account ON account.id = account_move_line.account_id
            WHERE {where_clause}
            AND account.internal_type IN ('receivable', 'payable')
            GROUP BY account_move_line.partner_id, account.code, account_move_line.date
        ''', where_params)

        partners_accounts = {}
        for vals in self._cr.dictfetchall():
            partner_id = vals['partner_id']
            account_code = vals['code']
            partner_account_code_balances = partners_accounts.setdefault(partner_id, {}).setdefault(account_code, {
                'code': account_code,
                'opening_balance': 0,
                'closing_balance': 0,
            })
            partner_account_code_balances['opening_balance'] += vals['opening_balance']
            partner_account_code_balances['closing_balance'] += vals['closing_balance']

        return partners_accounts
