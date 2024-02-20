# -*- coding: utf-8 -*-
from odoo import fields, Command
from odoo.tests import tagged
from odoo import fields

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install', '-at_install')
class TestAccountReports(TestAccountReportsCommon):

    @classmethod
    def _reconcile_on(cls, lines, account):
        lines.filtered(lambda line: line.account_id == account and not line.reconciled).reconcile()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.liquidity_journal_1 = cls.company_data['default_journal_bank']
        cls.liquidity_account = cls.liquidity_journal_1.default_account_id
        cls.receivable_account_1 = cls.company_data['default_account_receivable']
        cls.revenue_account_1 = cls.company_data['default_account_revenue']

        # Invoice having two receivable lines on the same account.

        invoice = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': '2016-01-01',
            'journal_id': cls.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'debit': 345.0,     'credit': 0.0,      'account_id': cls.receivable_account_1.id}),
                (0, 0, {'debit': 805.0,     'credit': 0.0,      'account_id': cls.receivable_account_1.id}),
                (0, 0, {'debit': 0.0,       'credit': 1150.0,   'account_id': cls.revenue_account_1.id}),
            ],
        })
        invoice.action_post()

        # First payment (20% of the invoice).

        payment_1 = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': '2016-02-01',
            'journal_id': cls.liquidity_journal_1.id,
            'line_ids': [
                (0, 0, {'debit': 0.0,       'credit': 230.0,    'account_id': cls.receivable_account_1.id}),
                (0, 0, {'debit': 230.0,     'credit': 0.0,      'account_id': cls.liquidity_account.id}),
            ],
        })
        payment_1.action_post()

        cls._reconcile_on((invoice + payment_1).line_ids, cls.receivable_account_1)

        # Second payment (also 20% but will produce two partials, one on each receivable line).

        payment_2 = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': '2016-03-01',
            'journal_id': cls.liquidity_journal_1.id,
            'line_ids': [
                (0, 0, {'debit': 0.0,       'credit': 230.0,    'account_id': cls.receivable_account_1.id}),
                (0, 0, {'debit': 230.0,     'credit': 0.0,      'account_id': cls.liquidity_account.id}),
            ],
        })
        payment_2.action_post()

        cls._reconcile_on((invoice + payment_2).line_ids, cls.receivable_account_1)

    def test_general_ledger_cash_basis(self):
        # Check the cash basis option.
        self.env['res.currency'].search([('name', '!=', 'USD')]).with_context({'force_deactivate': True}).active = False
        report = self.env['account.general.ledger']
        options = self._init_options(report, fields.Date.from_string('2016-01-01'), fields.Date.from_string('2016-12-31'))
        options['cash_basis'] = True
        report = report.with_context(report._set_context(options))

        lines = report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                            Debit       Credit      Balance
            [   0,                              4,          5,          6],
            [
                # Accounts.
                ('101404 Bank',                 460.0,      0.0,        460.0),
                ('121000 Account Receivable',   460.0,      460.0,      0.0),
                ('400000 Product Sales',        0.0,        460.0,      -460.0),
                # Report Total.
                ('Total',                       920.0,      920.0,     0.0),
            ],
        )

        # Mark the '101200 Account Receivable' line to be unfolded.
        line_id = lines[1]['id']
        options['unfolded_lines'] = [line_id]
        options['cash_basis'] = False  # Because we are in the same transaction, the table temp_account_move_line still exists
        self.assertLinesValues(
            report._get_lines(options, line_id=line_id),
            # pylint: disable=C0326
            #   Name                                    Date            Debit           Credit          Balance
            [   0,                                      1,                    4,             5,             6],
            [
                # Account.
                ('121000 Account Receivable',           '',              460.00,        460.00,          0.00),
                ('Initial Balance',                     '',                0.00,          0.00,          0.00),
                # Account Move Lines.
                ('MISC/2016/01/0001',                   '02/01/2016',     69.00,            '',         69.00),
                ('MISC/2016/01/0001',                   '02/01/2016',    161.00,            '',        230.00),
                ('BNK1/2016/02/0001',                   '02/01/2016',        '',        230.00,          0.00),
                ('MISC/2016/01/0001',                   '03/01/2016',     34.50,            '',         34.50),
                ('MISC/2016/01/0001',                   '03/01/2016',     34.50,            '',         69.00),
                ('MISC/2016/01/0001',                   '03/01/2016',     80.50,            '',        149.50),
                ('MISC/2016/01/0001',                   '03/01/2016',     80.50,            '',        230.00),
                ('BNK1/2016/03/0001',                   '03/01/2016',        '',        230.00,          0.00),
                # Account Total.
                ('Total 121000 Account Receivable',     '',              460.00,        460.00,          0.00),
            ],
        )

    def test_balance_sheet_cash_basis(self):
        # Check the cash basis option.
        report = self.env.ref('account_reports.account_financial_report_balancesheet0')
        options = self._init_options(report, fields.Date.from_string('2016-01-01'), fields.Date.from_string('2016-12-31'))
        options['cash_basis'] = True
        report = report.with_context(report._set_context(options))

        self.assertLinesValues(
            report._get_table(options)[1],
            #   Name                                            Balance
            [   0,                                              1],
            [
                ('ASSETS',                                      460.0),
                ('Current Assets',                              460.0),
                ('Bank and Cash Accounts',                      460.0),
                ('Receivables',                                 0.0),
                ('Current Assets',                              0.0),
                ('Prepayments',                                 0.0),
                ('Total Current Assets',                        460.0),
                ('Plus Fixed Assets',                           0.0),
                ('Plus Non-current Assets',                     0.0),
                ('Total ASSETS',                                460.0),

                ('LIABILITIES',                                 0.0),
                ('Current Liabilities',                         0.0),
                ('Current Liabilities',                         0.0),
                ('Payables',                                    0.0),
                ('Total Current Liabilities',                   0.0),
                ('Plus Non-current Liabilities',                0.0),
                ('Total LIABILITIES',                           0.0),

                ('EQUITY',                                      460.0),
                ('Unallocated Earnings',                        460.0),
                ('Current Year Unallocated Earnings',           460.0),
                ('Current Year Earnings',                       460.0),
                ('Current Year Allocated Earnings',             0.0),
                ('Total Current Year Unallocated Earnings',     460.0),
                ('Previous Years Unallocated Earnings',         0.0),
                ('Total Unallocated Earnings',                  460.0),
                ('Retained Earnings',                           0.0),
                ('Total EQUITY',                                460.0),

                ('LIABILITIES + EQUITY',                        460.0),
            ],
        )

    def test_cash_basis_payment_in_the_past(self):
        self.env['res.currency'].search([('name', '!=', 'USD')]).with_context({'force_deactivate': True}).active = False

        payment_date = fields.Date.from_string('2010-01-01')
        invoice_date = fields.Date.from_string('2011-01-01')

        invoice = self.init_invoice('out_invoice', amounts=[100.0], partner=self.partner_a, invoice_date=invoice_date, post=True)
        self.env['account.payment.register'].with_context(active_ids=invoice.ids, active_model='account.move').create({
            'payment_date': payment_date,
        })._create_payments()

        # Check the impact in the reports: the invoice date should be the one the invoice appears at, since it greater than the payment's
        report = self.env['account.general.ledger']

        options = self._init_options(report, payment_date, payment_date)
        options['cash_basis'] = True
        report = report.with_context(report._set_context(options))

        self.assertLinesValues(
            # pylint: disable=C0326
            report._get_lines(options),
            #   Name                                     Debit           Credit          Balance
            [   0,                                       4,              5,              6],
            [
                # Accounts.
                ('101402 Outstanding Receipts',        115,              0,            115),
                ('121000 Account Receivable',            0,            115,           -115),
                # Report Total.
                ('Total',                              115,            115,              0),
            ],
        )

        # Delete the temporary cash basis table manually in order to run another _get_lines in the same transaction
        self.env.cr.execute("""
            DROP TABLE temp_account_move_line
        """)

        options = self._init_options(report, invoice_date, invoice_date)
        options['cash_basis'] = True
        report = report.with_context(report._set_context(options))

        self.assertLinesValues(
            # pylint: disable=C0326
            report._get_lines(options),
            #   Name                                     Debit           Credit          Balance
            [   0,                                       4,              5,              6],
            [
                # Accounts.
                ('101402 Outstanding Receipts',        115,              0,            115),
                ('121000 Account Receivable',          115,            115,              0),
                ('251000 Tax Received',                  0,             15,            -15),
                ('400000 Product Sales',                 0,            100,           -100),
                # Report Total.
                ('Total',                              230,            230,              0),
            ],
        )

    def test_cash_basis_ar_ap_both_in_debit_and_credit(self):
        other_revenue = self.revenue_account_1.copy(default={'name': 'Other Income', 'code': '499000'})

        moves = self.env['account.move'].create([{
            'move_type': 'entry',
            'date': '2000-01-01',
            'journal_id': self.company_data['default_journal_misc'].id,
            'line_ids': [
                # pylint: disable=C0326
                Command.create({'name': '1',   'debit': 350.0,   'credit': 0.0,     'account_id': self.receivable_account_1.id}),
                Command.create({'name': '2',   'debit': 0.0,     'credit': 150.0,   'account_id': self.receivable_account_1.id}),
                Command.create({'name': '3',   'debit': 0.0,     'credit': 200.0,   'account_id': self.revenue_account_1.id}),
            ],
        }, {
            'move_type': 'entry',
            'date': '2001-01-01',
            'journal_id': self.company_data['default_journal_misc'].id,
            'line_ids': [
                # pylint: disable=C0326
                Command.create({'name': '4',   'debit': 350.0,   'credit': 0.0,     'account_id': self.liquidity_account.id}),
                Command.create({'name': '5',   'debit': 0.0,     'credit': 350.0,   'account_id': self.receivable_account_1.id}),
            ],
        }, {
            'move_type': 'entry',
            'date': '2002-01-01',
            'journal_id': self.company_data['default_journal_misc'].id,
            'line_ids': [
                # pylint: disable=C0326
                Command.create({'name': '6',   'debit': 150.0,   'credit': 0.0,     'account_id': self.receivable_account_1.id}),
                Command.create({'name': '7',   'debit': 0.0,     'credit': 150.0,   'account_id': other_revenue.id}),
            ],
        }])
        moves.action_post()

        ar1 = moves.line_ids.filtered(lambda x: x.name == '1')
        ar2 = moves.line_ids.filtered(lambda x: x.name == '2')
        ar5 = moves.line_ids.filtered(lambda x: x.name == '5')
        ar6 = moves.line_ids.filtered(lambda x: x.name == '6')

        (ar1 | ar5).reconcile()
        (ar2 | ar6).reconcile()

        # Check the impact in the reports: the invoice date should be the one the invoice appears at, since it greater than the payment's
        report = self.env['account.general.ledger']

        options = self._init_options(report, fields.Date.to_date('2000-01-01'), fields.Date.to_date('2000-01-01'))
        options['cash_basis'] = True
        report = report.with_context(report._set_context(options))

        self.assertLinesValues(
            # pylint: disable=C0326
            report._get_lines(options),
            #   Name                                     Debit           Credit          Balance
            [   0,                                       5,              6,              7],
            [
                # Accounts.
                # There should be no lines in this report.

                # Report Total.
                ('Total',                                0,              0,              0),
            ],
        )

        # Delete the temporary cash basis table manually in order to run another _get_lines in the same transaction
        self.env.cr.execute("DROP TABLE temp_account_move_line")

        options = self._init_options(report, fields.Date.to_date('2001-01-01'), fields.Date.to_date('2001-01-01'))
        options['cash_basis'] = True
        report = report.with_context(report._set_context(options))

        self.assertLinesValues(
            # pylint: disable=C0326
            report._get_lines(options),
            #   Name                                     Debit           Credit          Balance
            [   0,                                       5,              6,              7],
            [
                # Accounts.
                ('101404 Bank',                        350,              0,            350),
                ('121000 Account Receivable',          245,            455,           -210),
                ('400000 Product Sales',                 0,            140,           -140),
                # Report Total.
                ('Total',                              595,            595,              0),
            ],
        )

        # Delete the temporary cash basis table manually in order to run another _get_lines in the same transaction
        self.env.cr.execute("DROP TABLE temp_account_move_line")

        options = self._init_options(report, fields.Date.to_date('2002-01-01'), fields.Date.to_date('2002-01-01'))
        options['cash_basis'] = True
        report = report.with_context(report._set_context(options))

        self.assertLinesValues(
            # pylint: disable=C0326
            report._get_lines(options),
            #   Name                                     Debit           Credit          Balance
            [   0,                                       5,              6,              7],
            [
                # Accounts.
                ('101404 Bank',                        350,              0,            350),
                ('121000 Account Receivable',          500,            500,              0),
                ('400000 Product Sales',                 0,             60,            -60),
                ('499000 Other Income',                  0,            150,           -150),
                ('999999 Undistributed Profits/Losses',  0,            140,           -140),
                # Report Total.
                ('Total',                              850,            850,              0),
            ],
        )
        # Delete the temporary cash basis table manually in order to run another _get_lines in the same transaction
        self.env.cr.execute("DROP TABLE temp_account_move_line")

        options = self._init_options(report, fields.Date.to_date('2000-01-01'), fields.Date.to_date('2002-12-31'))
        options['cash_basis'] = True
        report = report.with_context(report._set_context(options))

        self.assertLinesValues(
            # pylint: disable=C0326
            report._get_lines(options),
            #   Name                                     Debit           Credit          Balance
            [   0,                                       5,              6,              7],
            [
                # Accounts.
                ('101404 Bank',                        350,              0,            350),
                ('121000 Account Receivable',          500,            500,              0),
                ('400000 Product Sales',                 0,            200,           -200),
                ('499000 Other Income',                  0,            150,           -150),
                # Report Total.
                ('Total',                              850,            850,              0),
            ],
        )
