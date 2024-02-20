# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.addons.website.tools import MockRequest
from odoo.addons.website_sale_account_taxcloud.controllers.main import WebsiteSale, PaymentPortal
from odoo.tests.common import TransactionCase


class TestWebsiteSaleTaxCloud(TransactionCase):

    def setUp(self):
        super().setUp()

        self.website = self.env['website'].browse(1)
        self.WebsiteSaleController = WebsiteSale()
        self.PaymentPortalController = PaymentPortal()

        self.public_user = self.env.ref('base.public_user')

        self.acquirer = self.env.ref('payment.payment_acquirer_transfer')

        self.fiscal_position = self.env['account.fiscal.position'].create({
            'name': 'BurgerLand',
            'is_taxcloud': True,
        })

        self.product = self.env['product.product'].create({
            'name': 'A',
            'list_price': 100,
            'sale_ok': True,
            'taxes_id': False,
            'website_published': True,
        })

    def _verify_address(self, *args):
        return {
            'apiLoginID': '',
            'apiKey': '',
            'Address1': '',
            'Address2': '',
            'City': '',
            "State": '',
            "Zip5": '',
            "Zip4": '',
        }

    def _get_all_taxes_values(self):
        return {'values': {0: 10}}

    def test_recompute_taxes_before_payment(self):
        """
        Make sure that taxes are recomputed before payment
        """

        website = self.website.with_user(self.public_user)
        with \
                patch('odoo.addons.account_taxcloud.models.taxcloud_request.TaxCloudRequest.verify_address', self._verify_address),\
                patch('odoo.addons.account_taxcloud.models.taxcloud_request.TaxCloudRequest.get_all_taxes_values', self._get_all_taxes_values),\
                MockRequest(self.product.with_user(self.public_user).env, website=website):

            self.WebsiteSaleController.cart_update_json(
                product_id=self.product.id, add_qty=1)

            sale_order = website.sale_get_order()
            sale_order.fiscal_position_id = self.fiscal_position.id
            sale_order.access_token = 'test_token'

            self.assertFalse(sale_order.order_line[0].tax_id)

            with patch.object(type(sale_order), '_get_TaxCloudRequest', return_value=sale_order._get_TaxCloudRequest("id", "api_key")):

                self.PaymentPortalController.shop_payment_transaction(
                    sale_order.id,
                    sale_order.access_token,
                    amount=110,
                    payment_option_id=self.acquirer.id,
                    tokenization_requested=True,
                    flow='direct',
                    currency_id=sale_order.currency_id.id,
                    partner_id=sale_order.partner_id.id,
                    landing_route='Test'
                )

            self.assertTrue(sale_order.order_line[0].tax_id)
