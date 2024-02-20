# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.account_reports.tests.account_sales_report_common import AccountSalesReportCommon
from odoo.tests import tagged
from freezegun import freeze_time


@tagged('post_install_l10n', 'post_install', '-at_install')
class BelgiumPartnerVATListingTest(AccountSalesReportCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref='l10n_be.l10nbe_chart_template'):
        super().setUpClass(chart_template_ref)

    @classmethod
    def setup_company_data(cls, company_name, chart_template=None, **kwargs):
        res = super().setup_company_data(company_name, chart_template=chart_template, **kwargs)
        res['company'].update({
            'country_id': cls.env.ref('base.be').id,
            'vat': 'BE0477472701',
        })
        res['company'].partner_id.update({
            'email': 'jsmith@mail.com',
            'phone': '+32475123456',
        })
        return res

    @freeze_time('2019-12-31')
    def test_generate_xml_minimal(self):
        report = self.env['l10n.be.report.partner.vat.listing']
        options = report._get_options(None)

        # The sequence changes between execution of the test. To handle that, we increase by 1 more, so we can get its value here
        sequence_number = self.env['ir.sequence'].next_by_code('declarantnum')
        ref = f"0477472701{str(int(sequence_number) + 1).zfill(4)[-4:]}"

        # This is the minimum expected from the belgian tax report xml.
        # As no values are in the report, we only find the grid 71 which is always expected to be present.
        expected_xml = """
            <ns2:ClientListingConsignment xmlns="http://www.minfin.fgov.be/InputCommon" xmlns:ns2="http://www.minfin.fgov.be/ClientListingConsignment" ClientListingsNbr="1">
                <ns2:ClientListing SequenceNumber="1" ClientsNbr="0" DeclarantReference="%s" TurnOverSum="0.00" VATAmountSum="0.00">
                    <ns2:Declarant>
                        <VATNumber>0477472701</VATNumber>
                        <Name>company_1_data</Name>
                        <Street></Street>
                        <PostCode></PostCode>
                        <City></City>
                        <CountryCode>BE</CountryCode>
                        <EmailAddress>jsmith@mail.com</EmailAddress>
                        <Phone>+32475123456</Phone>
                    </ns2:Declarant>
                    <ns2:Period>2019</ns2:Period>
                    <ns2:Comment></ns2:Comment>
                </ns2:ClientListing>
            </ns2:ClientListingConsignment>
        """ % ref

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(report.get_xml(options)),
            self.get_xml_tree_from_string(expected_xml)
        )

    @freeze_time('2019-12-31')
    def test_generate_xml_minimal_with_representative(self):
        company = self.env.company
        report = self.env['l10n.be.report.partner.vat.listing']
        options = report._get_options(None)

        # Create a new partner for the representative and link it to the company.
        representative = self.env['res.partner'].create({
            'company_type': 'company',
            'name': 'Fidu BE',
            'street': 'Fidu Street 123',
            'city': 'Brussels',
            'zip': '1000',
            'country_id': self.env.ref('base.be').id,
            'vat': 'BE0477472701',
            'mobile': '+32470123456',
            'email': 'info@fidu.be',
        })
        company.account_representative_id = representative.id

        # The sequence changes between execution of the test. To handle that, we increase by 1 more, so we can get its value here
        sequence_number = self.env['ir.sequence'].next_by_code('declarantnum')
        ref = f"0477472701{str(int(sequence_number) + 1).zfill(4)[-4:]}"

        # This is the minimum expected from the belgian tax report XML.
        # Only the representative node has been added to make sure it appears in the XML.
        expected_xml = """
            <ns2:ClientListingConsignment xmlns="http://www.minfin.fgov.be/InputCommon" xmlns:ns2="http://www.minfin.fgov.be/ClientListingConsignment" ClientListingsNbr="1">
                <ns2:Representative>
                    <RepresentativeID identificationType="NVAT" issuedBy="BE">0477472701</RepresentativeID>
                    <Name>Fidu BE</Name>
                    <Street>Fidu Street 123</Street>
                    <PostCode>1000</PostCode>
                    <City>Brussels</City>
                    <CountryCode>BE</CountryCode>
                    <EmailAddress>info@fidu.be</EmailAddress>
                    <Phone>+32470123456</Phone>
                </ns2:Representative>
                <ns2:ClientListing SequenceNumber="1" ClientsNbr="0" DeclarantReference="%s" TurnOverSum="0.00" VATAmountSum="0.00">
                    <ns2:Declarant>
                        <VATNumber>0477472701</VATNumber>
                        <Name>company_1_data</Name>
                        <Street></Street>
                        <PostCode></PostCode>
                        <City></City>
                        <CountryCode>BE</CountryCode>
                        <EmailAddress>jsmith@mail.com</EmailAddress>
                        <Phone>+32475123456</Phone>
                    </ns2:Declarant>
                    <ns2:Period>2019</ns2:Period>
                    <ns2:Comment></ns2:Comment>
                </ns2:ClientListing>
            </ns2:ClientListingConsignment>
        """ % ref

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(report.get_xml(options)),
            self.get_xml_tree_from_string(expected_xml)
        )
