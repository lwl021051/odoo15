from odoo import models


class account_journal(models.Model):
    _inherit = "account.journal"

    def action_open_reconcile(self):
        if self.type in ['bank', 'cash']:
            # Open reconciliation view for bank statements belonging to this journal
            Reconciliation = self.env['account.reconciliation.widget']
            bank_stmt_line_ids = Reconciliation.get_reconciliation_initial_line_ids(journals=self)
            return {
                'type': 'ir.actions.client',
                'tag': 'bank_statement_reconciliation_view',
                'context': {'statement_line_ids': bank_stmt_line_ids, 'company_ids': self.mapped('company_id').ids},
            }
        else:
            # Open reconciliation view for customers/suppliers
            action_context = {'show_mode_selector': False, 'company_ids': self.mapped('company_id').ids}
            if self.type == 'sale':
                action_context.update({'mode': 'customers'})
            elif self.type == 'purchase':
                action_context.update({'mode': 'suppliers'})
            return {
                'type': 'ir.actions.client',
                'tag': 'manual_reconciliation_view',
                'context': action_context,
            }

    def action_open_to_check(self):
        self.ensure_one()
        ids = self.to_check_ids().ids
        action_context = {'show_mode_selector': False, 'company_ids': self.mapped('company_id').ids}
        action_context.update({'suspense_moves_mode': True})
        action_context.update({'statement_line_ids': ids})
        return {
            'type': 'ir.actions.client',
            'tag': 'bank_statement_reconciliation_view',
            'context': action_context,
        }
