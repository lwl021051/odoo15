# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import math
import pytz

from datetime import datetime, timedelta, time, date
from odoo import api, fields, models, _
from odoo.tools import format_time
from odoo.addons.resource.models.resource import float_to_time
from odoo.exceptions import ValidationError


class PlanningTemplate(models.Model):
    _name = 'planning.slot.template'
    _description = "Shift Template"
    _order = "sequence"

    active = fields.Boolean('Active', default=True)
    name = fields.Char('Hours', compute="_compute_name")
    sequence = fields.Integer('Sequence', index=True)
    role_id = fields.Many2one('planning.role', string="Role")
    start_time = fields.Float('Start Hour', default=0, group_operator=None)
    duration = fields.Float('Duration (Hours)', default=0, group_operator=None)

    _sql_constraints = [
        ('check_start_time_lower_than_24', 'CHECK(start_time <= 24)', 'You cannot have a start hour greater than 24'),
        ('check_start_time_positive', 'CHECK(start_time >= 0)', 'Start hour must be a positive number'),
        ('check_duration_positive', 'CHECK(duration >= 0)', 'You cannot have a negative duration')
    ]

    # remove me in master, and update the sql contraint
    @api.constrains('start_time')
    def _validate_start_time(self):
        if self.filtered(lambda x: x.start_time >= 24):
            raise ValidationError(_('You cannot have a start hour greater than 24.'))

    @api.constrains('duration')
    def _validate_duration(self):
        try:
            for shift_template in self:
                datetime.today() + shift_template._get_duration()
        except OverflowError:
            raise ValidationError(_("The selected duration creates a date too far into the future."))

    @api.depends('start_time', 'duration')
    def _compute_name(self):
        calendar = self.env.company.resource_calendar_id
        user_tz = pytz.timezone(self.env['planning.slot']._get_tz())
        today = date.today()
        for shift_template in self:
            if not 0 <= shift_template.start_time < 24:
                raise ValidationError(_('The start hour must be greater or equal to 0 and lower than 24.'))
            start_time = time(hour=int(shift_template.start_time), minute=round(math.modf(shift_template.start_time)[0] / (1 / 60.0)))
            start_datetime = user_tz.localize(datetime.combine(today, start_time))
            duration_days, end_time = self._get_company_work_duration_data(calendar, start_datetime, shift_template.duration)
            if duration_days is None:
                shift_template.name = '%s - %s' % (
                    format_time(shift_template.env, start_time, time_format='short').replace(':00 ', ' '),
                    _('%s hours', shift_template.duration),
                )
                continue
            end_time = time(hour=int(end_time), minute=round(math.modf(end_time)[0] / (1 / 60.0)))
            shift_template.name = '%s - %s %s' % (
                format_time(shift_template.env, start_time, time_format='short').replace(':00 ', ' '),
                format_time(shift_template.env, end_time, time_format='short').replace(':00 ', ' '),
                _('(%s days span)') % (duration_days) if duration_days > 1 else ''
            )

    @api.model
    def _get_company_work_duration_data(self, calendar, start_datetime, duration):
        """"
            Taking company's working calendar into account get the `hours` and
            `days` from start_time and duration expressed in time and hours.

            :param start_time: reference time
            :param duration: reference duration in hours

            Returns a tuple (duration, end_time) expressed as days and as hours.
        """
        end_datetime = calendar.plan_hours(duration, start_datetime, compute_leaves=True)
        if end_datetime is False:
            return (None, None)  # the duration is too long, plan_hours is unable to compute it
        if duration == 0 and start_datetime.hour == 0:
            end_datetime = end_datetime.replace(hour=0)
        return (
            math.ceil(calendar.get_work_duration_data(start_datetime, end_datetime)['days']),
            timedelta(hours=end_datetime.hour, minutes=end_datetime.minute).total_seconds() / 3600,
        )

    def name_get(self):
        result = []
        for shift_template in self:
            name = '%s %s' % (
                shift_template.name,
                shift_template.role_id.name if shift_template.role_id.name is not False else ''
            )
            result.append([shift_template.id, name])
        return result

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        res = []
        for data in super(PlanningTemplate, self).read_group(domain, fields, groupby, offset, limit, orderby, lazy):
            if 'start_time' in data:
                data['start_time'] = float_to_time(data['start_time']).strftime('%H:%M')
            res.append(data)

        return res

    def _get_duration(self):
        self.ensure_one()
        return timedelta(hours=int(self.duration), minutes=round(math.modf(self.duration)[0] / (1 / 60.0)))
