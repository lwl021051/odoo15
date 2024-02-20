# -*- coding: utf-8 -*-
import datetime
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon
from odoo.tests import tagged
from unittest.mock import patch


@tagged('post_install', '-at_install')
class TestSubscriptionSEPA(TestSubscriptionCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        if not cls.env.ref('base.module_payment_sepa_direct_debit').state == 'installed':
            return
        cls.company_data['company'].country_id = cls.env.ref('base.us')

        cls.sepa = cls.env.ref('payment.payment_acquirer_sepa_direct_debit')
        bank_ing = cls.env['res.bank'].create({
            'name': 'ING',
            'bic': 'BBRUBEBB',
        })

        bank_account = cls.env['res.partner.bank'].create({
            'acc_number': 'NL91 ABNA 0417 1643 00',
            'partner_id': cls.env.company.partner_id.id,
            'bank_id': bank_ing.id,
        })
        journal = cls.env['account.journal'].create({
            'name': 'Bank SEPA',
            'type': 'bank',
            'code': 'BNKSEPA',
            'inbound_payment_method_line_ids': [(4, cls.env.ref('account_sepa_direct_debit.payment_method_sdd').id)],
            'bank_account_id': bank_account.id,
        })

        cls.company_data['company'].write({
            'sdd_creditor_identifier': 'BE34ZZZ12D87654321',
        })

        cls.sepa.sudo().write({
            'journal_id': journal.id,
            'company_id': cls.company_data['company'].id,
            'state': 'enabled',
        })

        cls.partner_bank = cls.env['res.partner.bank'].create({
            'acc_number': 'BE17412614919710',
            'partner_id': cls.user_portal.partner_id.id,
            'company_id': cls.env.company.id,
        })

        cls.mandate = cls.env['sdd.mandate'].create({
            'partner_id': cls.user_portal.partner_id.id,
            'company_id': cls.env.company.id,
            'partner_bank_id': cls.partner_bank.id,
            'start_date': fields.date.today(),
            'payment_journal_id': cls.sepa.journal_id.id,
            'verified': True,
            'state': 'active',
        })

        cls.payment_token = cls.env['payment.token'].create({
            'name': 'BE17412614919710',
            'partner_id': cls.user_portal.partner_id.id,
            'acquirer_id': cls.sepa.id,
            'acquirer_ref': cls.mandate.name,
            'sdd_mandate_id': cls.mandate.id,
        })

    def test_01_recurring_invoice_sepa(self):
        if not self.env.ref('base.module_payment_sepa_direct_debit').state == 'installed':
            return
        self.user_portal.partner_id.write({
            'property_account_receivable_id': self.company_data['default_account_receivable'].id,
            'property_account_payable_id': self.company_data['default_account_payable'].id,
        })
        self.subscription_tmpl.write({'invoice_mail_template_id': self.env.ref('sale_subscription.mail_template_subscription_invoice').id})
        self.subscription.write({
            'partner_id': self.user_portal.partner_id.id,
            'recurring_next_date': fields.Date.to_string(datetime.date.today()),
            'template_id': self.subscription_tmpl.id,
            'company_id': self.env.company.id,
            'payment_token_id': self.payment_token.id,
            'recurring_invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'name': 'TestRecurringLine', 'price_unit': 50, 'uom_id': self.product.uom_id.id})],
            'stage_id': self.ref('sale_subscription.sale_subscription_stage_in_progress'),
        })

        base_recurring_next_date = self.subscription.recurring_next_date

        self.send_success_count = 0
        self.subscription_tmpl.write({'payment_mode': 'success_payment'})

        sub = self.subscription.copy()
        with patch('odoo.addons.sale_subscription.models.sale_subscription.SaleSubscription.send_success_mail', wraps=self._mock_send_success_mail):
            sub.with_context(auto_commit=False)._recurring_create_invoice(automatic=True)

            # Check that next invoice date is correctly updated
            self.assertEqual(sub.recurring_next_date, base_recurring_next_date + relativedelta(months=1),
                        'Invoice recurring_next_date should be next month')

            # check invoice amount and taxes
            invoice_id = sub.action_subscription_invoice()['res_id']
            invoice = self.env['account.move'].browse(invoice_id)

            # check transaction state
            tx = invoice.mapped('transaction_ids')
            payment = tx.payment_id
            self.assertEqual(len(tx), 1, 'a single transaction should be created')
            self.assertEqual(tx.state, 'pending', 'transaction should be pending')
            self.assertEqual(payment.state, 'posted', 'payment should be posted')
            self.assertTrue(invoice.payment_state in ('in_payment', 'paid'), 'invoice should be paid')
            self.assertEqual(invoice.state, 'posted', 'move should be posted')
            # A payment reference should be linked
            self.assertTrue(invoice.ref != "", 'A payment reference should be linked in the invoice')

            # reconcile the payment
            bank_journal = payment.journal_id
            bank_stmt = self.env['account.bank.statement'].create({
                'journal_id': bank_journal.id,
                'date': payment.date,
                'name': payment.name,
            })
            bank_stmt_line = self.env['account.bank.statement.line'].create({
                'statement_id': bank_stmt.id,
                'partner_id': self.user_portal.partner_id.id,
                'amount': payment.amount,
                'date': payment.date,
                'payment_ref': payment.name,
            })
            bank_stmt.button_post()
            move_line = payment.line_ids.filtered(lambda aml: aml.account_id.internal_type not in ('receivable', 'payable'))
            bank_stmt_line.reconcile([{'id': move_line.id}])

            # check post-reconciliation states
            self.assertEqual(payment.is_matched, True, 'payment should be reconciled')
            self.assertEqual(tx.state, 'done', 'transaction should be done')
            self.assertEqual(invoice.state, 'posted', 'invoice should be posted')
            self.assertEqual(invoice.payment_state, 'paid', 'invoice should be paid')

    def _mock_send_success_mail(self, tx, invoice):
        self.send_success_count += 1
