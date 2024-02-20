# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Accounting',
    'version': '1.1',
    'category': 'Accounting/Accounting',
    'sequence': 30,
    'summary': 'Manage financial and analytic accounting',
    'description': """""",
    'website': '',
    'depends': ['account', 'web_tour'],
    'data': [
        'data/account_accountant_data.xml',
        'data/digest_data.xml',
        'security/ir.model.access.csv',
        'security/account_accountant_security.xml',
        'views/account_account_views.xml',
        'views/account_bank_statement_views.xml',
        'views/account_fiscal_year_view.xml',
        'views/account_journal_dashboard_views.xml',
        'views/account_move_views.xml',
        'views/account_payment_views.xml',
        'views/account_accountant_menuitems.xml',
        'views/digest_views.xml',
        'views/res_config_settings_views.xml',
        'views/product_views.xml',
        'wizard/account_change_lock_date.xml',
        'wizard/reconcile_model_wizard.xml',
    ],
    'demo': ['data/account_accountant_demo.xml'],
    'test': [],
    'installable': True,
    'auto_install': False,
    'application': True,
    'post_init_hook': '_account_accountant_post_init',
    'uninstall_hook': "uninstall_hook",
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend': [
            'account_accountant/static/src/scss/move_line_list_view.scss',
            'account_accountant/static/src/js/move_line_list_view.js',
            'account_accountant/static/src/js/tours/account_accountant.js',
            'account_accountant/static/src/js/reconciliation/reconciliation_action.js',
            'account_accountant/static/src/js/reconciliation/reconciliation_model.js',
            'account_accountant/static/src/js/reconciliation/reconciliation_renderer.js',
            'account_accountant/static/src/js/reconciliation/reconciliation_rainbowman_component.js',
        ],
        'web.assets_tests': [
            'account_accountant/static/tests/tours/**/*',
        ],
        'web.qunit_suite_tests': [
            'account_accountant/static/tests/reconciliation_tests.js',
            'account_accountant/static/tests/move_line_list_tests.js',
        ],
        'web.assets_qweb': [
            'account_accountant/static/src/xml/**/*',
        ],
    }
}