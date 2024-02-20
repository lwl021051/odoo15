# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import Command
from odoo.tests import tagged

from .common import SepaDirectDebitCommon

@tagged('post_install', '-at_install')
class TestSepaDirectDebit(SepaDirectDebitCommon):

    def test_sepa_direct_debit_s2s_process(self):
        token = self.create_token(
            sdd_mandate_id=self.mandate.id,
            acquirer_ref=self.mandate.name,
        )

        tx = self.create_transaction(
            flow='direct',
            amount=10.0,
            token_id=token.id,
        )

        # 1. capture transaction
        tx._send_payment_request()

        self.assertEqual(tx.state, 'pending', 'payment transaction should be pending')
        self.assertEqual(tx.payment_id.state, 'posted', 'account payment should be posted')
        self.assertEqual(tx.payment_id.sdd_mandate_id.id, self.mandate.id)

        # 2. reconcile
        self.reconcile(tx.payment_id)

        self.assertEqual(tx.state, 'done', 'payment transaction should be done')

    def test_sepa_direct_debit_acquirer_in_batch_payment(self):
        """
        Test the xml generation when validating a batch payment
        with sdd acquirer payment method.
        """
        token = self.create_token(
            sdd_mandate_id=self.mandate.id,
            acquirer_ref=self.mandate.name,
        )

        tx = self.create_transaction(
            flow='direct',
            amount=10.0,
            token_id=token.id,
        )

        # 1. capture transaction
        tx._send_payment_request()

        self.assertEqual(tx.state, 'pending', 'payment transaction should be pending')
        self.assertEqual(tx.payment_id.state, 'posted', 'account payment should be posted')
        self.assertEqual(tx.payment_id.sdd_mandate_id.id, self.mandate.id)

        # 2. Make a batch with the payment
        payment = tx.payment_id
        batch_payment = self.env['account.batch.payment'].create(
            {
                'journal_id': payment.journal_id.id,
                'payment_method_id': payment.payment_method_id.id,
                'payment_ids': [
                    (Command.set(payment.ids))
                ],
            }
        )
        res = batch_payment.validate_batch_button()

        # 3. A wizard should be generated, with a file to export
        self.assertTrue(res)
        res_wizard = self.env[res.get('res_model', 'account.batch.download.wizard')].search([('id', '=', res.get('res_id'))])
        self.assertTrue(res_wizard.export_file)
