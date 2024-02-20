from odoo import api, models, _
from odoo.exceptions import RedirectWarning
from odoo.tools import float_repr

import stdnum.de.stnr
import stdnum.exceptions

from lxml import etree
from datetime import date, datetime


class AccountGenericTaxReport(models.AbstractModel):
    _inherit = 'account.generic.tax.report'

    def _get_reports_buttons(self, options):
        buttons = super(AccountGenericTaxReport, self)._get_reports_buttons(options)
        if self._get_report_country_code(options) == 'DE':
            buttons += [{'name': _('XML'), 'sequence': 3, 'action': 'print_xml', 'file_export_type': _('XML')}]
        return buttons

    @api.model
    def _redirect_to_misconfigured_company_number(self, message):
        """ Raises a RedirectWarning informing the user his company is missing configuration, redirecting him to the
         tree view of res.company
        """
        action = self.env.ref('base.action_res_company_form')

        raise RedirectWarning(
            message,
            action.id,
            _("Configure your company"),
        )

    def get_xml(self, options):
        if self._get_report_country_code(options) != 'DE':
            return super(AccountGenericTaxReport, self).get_xml(options)

        if self.env.company.l10n_de_stnr:
            try:
                steuer_nummer = stdnum.de.stnr.to_country_number(self.env.company.l10n_de_stnr, self.env.company.state_id.with_context(lang='de_DE').name)
            except stdnum.exceptions.InvalidComponent:
                self._redirect_to_misconfigured_company_number(_("Your company's SteuerNummer is not compatible with your state"))
            except stdnum.exceptions.InvalidFormat:
                if stdnum.de.stnr.is_valid(self.env.company.l10n_de_stnr, self.env.company.state_id.with_context(lang='de_DE').name):
                    # the SteuerNummer is already in the right format, and so, can't be converted
                    steuer_nummer = self.env.company.l10n_de_stnr
                else:
                    self._redirect_to_misconfigured_company_number(_("Your company's SteuerNummer is not valid"))
        else:
            self._redirect_to_misconfigured_company_number(_("Your company's SteuerNummer field should be filled"))

        ctx = self._set_context(options)
        report_lines = self.with_context(ctx)._get_lines(options)

        template_context = {}
        date_to = datetime.strptime(options['date']['date_to'], '%Y-%m-%d')
        template_context['year'] = date_to.year
        if options['date']['period_type'] == 'month':
            template_context['period'] = date_to.strftime("%m")
        elif options['date']['period_type'] == 'quarter':
            month_end = int(date_to.month)
            if month_end % 3 != 0:
                raise ValueError('Quarter not supported')
            # For quarters, the period should be 41, 42, 43, 44 depending on the quarter.
            template_context['period'] = int(month_end / 3 + 40)
        template_context['creation_date'] = date.today().strftime("%Y%m%d")
        template_context['company'] = self._get_sender_company_for_export(options)

        qweb = self.env['ir.qweb']
        doc = qweb._render('l10n_de_reports.tax_export_xml', values=template_context)
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.fromstring(doc, parser)

        taxes = tree.xpath('//Umsatzsteuervoranmeldung')[0]
        tax_number = tree.xpath('//Umsatzsteuervoranmeldung/Steuernummer')[0]
        tax_number.text = steuer_nummer

        # Add the values dynamically. We do it here because the tag is generated from the code and
        # Qweb doesn't allow dynamically generated tags.

        for line in report_lines:
            if not line['line_code']:
                continue
            # all "Kz" may be supplied as negative, except "Kz37", "Kz39", "Kz50"
            line_balance = line['columns'][0]['balance']
            if line_balance and (line['line_code'] not in ("37", "39", "50") or line_balance > 0):
                elem = etree.SubElement(taxes, "Kz" + line['line_code'])
                # These can not be supplied with decimals
                if line['line_code'] in ("21", "35", "41", "42", "43", "44", "45", "46", "48", "49", "50", "60", "73",
                                 "76", "77", "81", "84", "86", "87", "89", "91", "93", "90", "94", "95"):
                    elem.text = float_repr(int(line_balance), 0)
                elif line['line_code'] in ("66", "61", "62", "67", "63", "59", "64",):
                    # These are taxes that are on the wrong sign on the report compared to what should be exported
                    elem.text = float_repr(- line_balance, 2).replace('.', ',')
                else:
                    elem.text = float_repr(line_balance, 2).replace('.', ',')

            # "kz83" must be supplied with 0.00 if it doesn't have balance
            elif line['line_code'] == "83":
                elem = etree.SubElement(taxes, "Kz" + line['line_code'])
                elem.text = "0,00"

        return etree.tostring(tree, pretty_print=True, standalone=False, encoding='ISO-8859-1',)
