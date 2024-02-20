# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime, timedelta
from freezegun import freeze_time
from werkzeug.urls import url_encode, url_join

import odoo
from odoo.addons.appointment.tests.common import AppointmentCommon
from odoo.addons.http_routing.models.ir_http import slug
from odoo.exceptions import ValidationError
from odoo.tests import tagged, users, HttpCase


@tagged('appointment_slots')
class AppointmentTest(AppointmentCommon, HttpCase):

    @freeze_time('2023-01-6')
    @users('apt_manager')
    def test_appointment_availability_with_show_as(self):
        """ Checks that if a normal event and custom event both set at the same time but
        the normal event is set as free then the custom meeting should be available and
        available_unique_slots will contains only available slots """

        employee = self.staff_employees[0]

        self.env["calendar.event"].create([
            {
                "name": "event-1",
                "start": datetime(2023, 6, 5, 8, 0),
                "stop": datetime(2023, 6, 5, 9, 0),
                "show_as": 'free',
                "partner_ids": employee.user_partner_id,
                "attendee_ids": [(0, 0, {
                    "state": "accepted",
                    "availability": "free",
                    "partner_id": employee.user_partner_id.id,
                })],
            }, {
                "name": "event-2",
                "start": datetime(2023, 6, 5, 12, 0),
                "stop": datetime(2023, 6, 5, 13, 0),
                "show_as": 'busy',
                "partner_ids": employee.user_partner_id,
                "attendee_ids": [(0, 0, {
                    "state": "accepted",
                    "availability": "busy",
                    "partner_id": employee.user_partner_id.id,
                })],
            },
        ])

        unique_slots = [{
            'allday': False,
            'start_datetime': datetime(2023, 6, 5, 8, 0),
            'end_datetime': datetime(2023, 6, 5, 9, 0),
        }, {
            'allday': False,
            'start_datetime': datetime(2023, 6, 5, 12, 0),
            'end_datetime': datetime(2023, 6, 5, 13, 0),
        }]

        apt_types = self.env['calendar.appointment.type'].create([
            {
                'category': 'custom',
                'name': 'Custom Meeting 1',
                'employee_ids': [(4, employee.id)],
                'slot_ids': [(0, 0, {
                    'allday': slot['allday'],
                    'end_datetime': slot['end_datetime'],
                    'slot_type': 'unique',
                    'start_datetime': slot['start_datetime'],
                    }) for slot in unique_slots
                ],
            }, {
                'category': 'custom',
                'name': 'Custom Meeting 2',
                'employee_ids': [(4, employee.id)],
                'slot_ids': [(0, 0, {
                    'allday': unique_slots[1]['allday'],
                    'end_datetime': unique_slots[1]['end_datetime'],
                    'slot_type': 'unique',
                    'start_datetime': unique_slots[1]['start_datetime'],
                    })
                ],
            },
        ])

        slots = apt_types[0]._get_appointment_slots('UTC')
        available_unique_slots = self._filter_appointment_slots(
            slots,
            filter_months=[(6, 2023)],
            filter_employees=employee)

        self.assertEqual(len(available_unique_slots), 1)

        for unique_slot, apt_type, is_available in zip(unique_slots, apt_types, [True, False]):
            self.assertEqual(
                apt_type._check_appointment_is_valid_slot(
                    employee,
                    'UTC',
                    unique_slot['start_datetime'],
                    1.0
                ),
                is_available
            )

            self.assertEqual(
                employee.user_partner_id.calendar_verify_availability(
                    unique_slot['start_datetime'],
                    unique_slot['end_datetime'],
                ),
                is_available
            )

    @users('apt_manager')
    def test_appointment_share(self):
        apt_types = self.env['calendar.appointment.type'].create([
            {
                'category': 'custom',
                'employee_ids': self.staff_employee_bxls,
                'name': 'Appointment 1',
            }, {
                'category': 'custom',
                'employee_ids': self.staff_employee_aust,
                'name': 'Appointment 2',
            },
        ])

        apt_share_wizard = self.env['calendar.appointment.share'].create({
            'appointment_type_ids' : apt_types[0],
        })
        self.assertEqual(apt_types[0].employee_ids, apt_share_wizard.employee_ids)

        apt_share_wizard.appointment_type_ids = apt_types[1]
        self.assertEqual(apt_types[1].employee_ids, apt_share_wizard.employee_ids)

    @users('apt_manager')
    def test_appointment_type_create(self):
        # Custom: current employee set as default, otherwise accepts only 1 employee
        apt_type = self.env['calendar.appointment.type'].create({
            'category': 'custom',
            'name': 'Custom without employee',
        })
        self.assertEqual(apt_type.employee_ids, self.apt_manager_employee)

        apt_type = self.env['calendar.appointment.type'].create({
            'category': 'custom',
            'employee_ids': [(4, self.staff_employees[0].id)],
            'name': 'Custom with employee',
        })
        self.assertEqual(apt_type.employee_ids, self.staff_employees[0])

        with self.assertRaises(ValidationError):
            self.env['calendar.appointment.type'].create({
                'category': 'custom',
                'employee_ids': self.staff_employees.ids,
                'name': 'Custom with employees',
            })

        # Work hours: only 1 / employee
        apt_type = self.env['calendar.appointment.type'].create({
            'category': 'work_hours',
            'name': 'Work hours on me',
        })
        self.assertEqual(apt_type.employee_ids, self.apt_manager_employee)

        with self.assertRaises(ValidationError):
            self.env['calendar.appointment.type'].create({
                'category': 'work_hours',
                'name': 'Work hours on me, duplicate',
            })

        with self.assertRaises(ValidationError):
            self.env['calendar.appointment.type'].create({
                'name': 'Work hours without employee',
                'category': 'work_hours',
                'employee_ids': [self.staff_employees.ids]
            })

    @freeze_time('2023-01-9')
    def test_booking_validity(self):
        """
        When confirming an appointment, we must recheck that it is indeed a valid slot,
        because the user can modify the date URL parameter used to book the appointment.
        We make sure the date is a valid slot, not outside of those specified by the employee,
        and that it's not an old valid slot (a slot that is valid, but it's in the past,
        so we shouldn't be able to book for a date that has already passed)
        """
        # add the timezone of the visitor on the session (same as appointment to simplify)
        session = self.authenticate(None, None)
        session['timezone'] = self.apt_type_bxls_2days.appointment_tz
        odoo.http.root.session_store.save(session)
        appointment = self.apt_type_bxls_2days
        appointment_url = url_join(appointment.get_base_url(), '/calendar/%s' % slug(appointment))
        appointment_info_url = "%s/info?" % appointment_url
        url_inside_of_slot = appointment_info_url + url_encode({
            'employee_id': self.staff_employee_bxls.id,
            'date_time': datetime(2023, 1, 9, 9, 0),  # 9/01/2023 is a Monday, there is a slot at 9:00
            'duration': 1,
        })
        response = self.url_open(url_inside_of_slot)
        self.assertEqual(response.status_code, 200, "Response should be Ok (200)")
        url_outside_of_slot = appointment_info_url + url_encode({
            'employee_id': self.staff_employee_bxls.id,
            'date_time': datetime(2023, 1, 9, 22, 0),  # 9/01/2023 is a Monday, there is no slot at 22:00
            'duration': 1,
        })
        response = self.url_open(url_outside_of_slot)
        self.assertEqual(response.status_code, 404, "Response should be Page Not Found (404)")
        url_inactive_past_slot = appointment_info_url + url_encode({
            'employee_id': self.staff_employee_bxls.id,
            'date_time': datetime(2023, 1, 2, 22, 0),
            # 2/01/2023 is a Monday, there is a slot at 9:00, but that Monday has already passed
            'duration': 1,
        })
        response = self.url_open(url_inactive_past_slot)
        self.assertEqual(response.status_code, 404, "Response should be Page Not Found (404)")

    @users('apt_manager')
    def test_generate_slots_recurring(self):
        """ Generates recurring slots, check begin and end slot boundaries. """
        apt_type = self.apt_type_bxls_2days.with_user(self.env.user)

        with freeze_time(self.reference_now):
            slots = apt_type._get_appointment_slots('Europe/Brussels')

        global_slots_startdate = self.reference_now_monthweekstart
        global_slots_enddate = date(2022, 3, 6)  # last day of last week of February
        self.assertSlots(
            slots,
            [{'name_formated': 'February 2022',
              'month_date': datetime(2022, 2, 1),
              'weeks_count': 5,  # 31/01 -> 28/02 (06/03)
             }
            ],
            {'enddate': global_slots_enddate,
             'startdate': global_slots_startdate,
             'slots_start_hours': [8, 9, 10, 11, 13],  # based on appointment type start hours of slots but 12 is pause midi
             'slots_startdate': self.reference_monday.date(),  # first Monday after reference_now
             'slots_weekdays_nowork': range(2, 7)  # working hours only on Monday/Tuesday (0, 1)
            }
        )

    @users('apt_manager')
    def test_generate_slots_recurring_midnight(self):
        """ Generates recurring slots, check around midnight """
        late_night_cal = self.env['resource.calendar'].sudo().create({
            'attendance_ids': [(0, 0, {
                'dayofweek': f'{day - 1}',
                'hour_from': hour,
                'hour_to': hour + 4,
                'name': f'Day {day} H {hour} {hour + 4}',
            }) for hour in [0, 20] for day in [1, 2, 3, 4]],
            'company_id': self.company_admin.id,
            'name': '00:00-04:00 and 20:00-00:00 on Mondays through Thursday',
            'tz': 'UTC',
        })

        # Current employee is Europe/Brussels
        current_employee_sudo = self.env.user.employee_id.sudo()
        current_employee_sudo.resource_calendar_id = late_night_cal
        current_employee_sudo.tz = 'UTC'

        apt_type = self.env['calendar.appointment.type'].create({
            'appointment_duration': 1,
            'appointment_tz': 'UTC',
            'category': 'website',
            'employee_ids': [(4, current_employee_sudo.id)],
            'name': 'Midnight Test',
            'max_schedule_days': 4,
            'min_cancellation_hours': 1,
            'min_schedule_hours': 0,
            'slot_ids': [
                (0, False, {'weekday': '1',
                            'start_hour': hour,
                            'end_hour': hour + 1,
                           })
                for hour in [0, 1, 2, 21, 22, 23]
            ] + [
                (0, False, {'weekday': '2',
                            'start_hour': hour,
                            'end_hour': hour + 1,
                           })
                for hour in [0, 1, 2]
            ] + [
                (0, False, {'weekday': '2',
                            'start_hour': 20,
                            'end_hour': 24,
                           })
            ] + [
                (0, False, {'weekday': '3',
                            'start_hour': hour,
                            'end_hour': hour + 5,
                           })
                for hour in [0, 19]
            ]
        })

        # freeze the day before, early enough to be able to schedule the first hour
        with freeze_time(self.reference_monday.replace(hour=1, minute=36)):
            slots = apt_type._get_appointment_slots('UTC')

        global_slots_startdate = self.reference_now_monthweekstart
        global_slots_enddate = date(2022, 3, 6)

        self.assertSlots(
            slots,
            [{'name_formated': 'February 2022',
              'month_date': datetime(2022, 2, 1),
              'weeks_count': 5,  # 31/01 -> 28/02 (06/03)
             }
            ],
            {'enddate': global_slots_enddate,
             'startdate': global_slots_startdate,
             'slots_day_specific': {self.reference_monday.date(): [
                    {'start': 2, 'end': 3},  # 02:00 is the first valid slot when the current time is 01:36
                    {'start': 21, 'end': 22},
                    {'start': 22, 'end': 23},
                    {'start': 23, 'end': 00},
                ], (self.reference_monday + timedelta(days=1)).date(): [
                    {'start': 0, 'end': 1},
                    {'start': 1, 'end': 2},
                    {'start': 2, 'end': 3},
                    {'start': 20, 'end': 21},
                    {'start': 21, 'end': 22},
                    {'start': 22, 'end': 23},
                    {'start': 23, 'end': 00},
                ], (self.reference_monday + timedelta(days=2)).date(): [
                    {'start': 0, 'end': 1},
                    {'start': 1, 'end': 2},
                    {'start': 2, 'end': 3},
                    {'start': 3, 'end': 4},  # slots start at 20 and end at 4 because of resource schedule
                    {'start': 20, 'end': 21},
                    {'start': 21, 'end': 22},
                    {'start': 22, 'end': 23},
                    {'start': 23, 'end': 00},
                ]},
             'slots_startdate': self.reference_monday,
            }
        )

    @users('apt_manager')
    def test_generate_slots_recurring_UTC(self):
        """ Generates recurring slots, check begin and end slot boundaries. Force
        UTC results event if everything is Europe/Brussels based. """
        apt_type = self.apt_type_bxls_2days.with_user(self.env.user)

        with freeze_time(self.reference_now):
            slots = apt_type._get_appointment_slots('UTC')

        global_slots_startdate = self.reference_now_monthweekstart
        global_slots_enddate = date(2022, 3, 6)  # last day of last week of February
        self.assertSlots(
            slots,
            [{'name_formated': 'February 2022',
              'month_date': datetime(2022, 2, 1),
              'weeks_count': 5,  # 31/01 -> 28/02 (06/03)
             }
            ],
            {'enddate': global_slots_enddate,
             'startdate': global_slots_startdate,
             'slots_start_hours': [7, 8, 9, 10, 12],  # based on appointment type start hours of slots but 12 is pause midi
             'slots_startdate': self.reference_monday.date(),  # first Monday after reference_now
             'slots_weekdays_nowork': range(2, 7)  # working hours only on Monday/Tuesday (0, 1)
            }
        )

    @users('apt_manager')
    def test_generate_slots_recurring_wleaves(self):
        """ Generates recurring slots, check begin and end slot boundaries
        with leaves involved. """
        apt_type = self.apt_type_bxls_2days.with_user(self.env.user)

        # create personal leaves
        _leaves = self._create_leaves(
            self.staff_user_bxls,
            [(self.reference_monday + timedelta(days=1),  # 2 hours first Tuesday
              self.reference_monday + timedelta(days=1, hours=2)),
             (self.reference_monday + timedelta(days=7), # next Monday: one hour
              self.reference_monday + timedelta(days=7, hours=1))
            ],
        )
        # add global leaves
        _leaves += self._create_leaves(
            self.env['res.users'],
            [(self.reference_monday + timedelta(days=8), # next Tuesday is bank holiday
              self.reference_monday + timedelta(days=8, hours=12))
            ],
            calendar=self.staff_user_bxls.resource_calendar_id,
        )

        with freeze_time(self.reference_now):
            slots = apt_type._get_appointment_slots('Europe/Brussels')

        global_slots_startdate = self.reference_now_monthweekstart
        global_slots_enddate = date(2022, 3, 6)  # last day of last week of February
        self.assertSlots(
            slots,
            [{'name_formated': 'February 2022',
              'month_date': datetime(2022, 2, 1),
              'weeks_count': 5,  # 31/01 -> 28/02 (06/03)
             }
            ],
            {'enddate': global_slots_enddate,
             'startdate': global_slots_startdate,
             'slots_day_specific': {
                (self.reference_monday + timedelta(days=1)).date(): [
                    {'end': 11, 'start': 10},
                    {'end': 12, 'start': 11},
                    {'end': 14, 'start': 13}
                ],  # leaves on 7-9 UTC
                (self.reference_monday + timedelta(days=7)).date(): [
                    {'end': 10, 'start': 9},
                    {'end': 11, 'start': 10},
                    {'end': 12, 'start': 11},
                    {'end': 14, 'start': 13}
                ],  # leaves on 7-8
                (self.reference_monday + timedelta(days=8)).date(): [],  # 12 hours long bank holiday
             },
             'slots_start_hours': [8, 9, 10, 11, 13],  # based on appointment type start hours of slots but 12 is pause midi
             'slots_startdate': self.reference_monday.date(),  # first Monday after reference_now
             'slots_weekdays_nowork': range(2, 7)  # working hours only on Monday/Tuesday (0, 1)
            }
        )

    @users('apt_manager')
    def test_generate_slots_recurring_wmeetings(self):
        """ Generates recurring slots, check begin and end slot boundaries
        with leaves involved. """
        apt_type = self.apt_type_bxls_2days.with_user(self.env.user)

        # create meetings
        _meetings = self._create_meetings(
            self.staff_user_bxls,
            [(self.reference_monday + timedelta(days=1),  # 3 hours first Tuesday
              self.reference_monday + timedelta(days=1, hours=3),
              False
             ),
             (self.reference_monday + timedelta(days=7), # next Monday: one full day
              self.reference_monday + timedelta(days=7, hours=1),
              True,
             ),
             (self.reference_monday + timedelta(days=8, hours=2), # 1 hour next Tuesday (9 UTC)
              self.reference_monday + timedelta(days=8, hours=3),
              False,
             ),
             (self.reference_monday + timedelta(days=8, hours=3), # 1 hour next Tuesday (10 UTC, declined)
              self.reference_monday + timedelta(days=8, hours=4),
              False,
             ),
             (self.reference_monday + timedelta(days=8, hours=5), # 2 hours next Tuesday (12 UTC)
              self.reference_monday + timedelta(days=8, hours=7),
              False,
             ),
            ]
        )
        attendee = _meetings[-2].attendee_ids.filtered(lambda att: att.partner_id == self.staff_user_bxls.partner_id)
        attendee.do_decline()

        with freeze_time(self.reference_now):
            slots = apt_type._get_appointment_slots('Europe/Brussels')

        global_slots_startdate = self.reference_now_monthweekstart
        global_slots_enddate = date(2022, 3, 6)  # last day of last week of February
        self.assertSlots(
            slots,
            [{'name_formated': 'February 2022',
              'month_date': datetime(2022, 2, 1),
              'weeks_count': 5,  # 31/01 -> 28/02 (06/03)
             }
            ],
            {'enddate': global_slots_enddate,
             'startdate': global_slots_startdate,
             'slots_day_specific': {
                (self.reference_monday + timedelta(days=1)).date(): [
                    {'end': 12, 'start': 11},
                    {'end': 14, 'start': 13},
                ],  # meetings on 7-10 UTC
                (self.reference_monday + timedelta(days=7)).date(): [],  # on meeting "allday"
                (self.reference_monday + timedelta(days=8)).date(): [
                    {'end': 9, 'start': 8},
                    {'end': 10, 'start': 9}, 
                    {'end': 12, 'start': 11},
                ],  # meetings 9-10 and 12-14
             },
             'slots_start_hours': [8, 9, 10, 11, 13],  # based on appointment type start hours of slots but 12 is pause midi
             'slots_startdate': self.reference_monday.date(),  # first Monday after reference_now
             'slots_weekdays_nowork': range(2, 7)  # working hours only on Monday/Tuesday (0, 1)
            }
        )

    @users('apt_manager')
    def test_generate_slots_unique(self):
        """ Check unique slots (note: custom appointment type does not check working
        hours). """
        unique_slots = [{
            'start_datetime': self.reference_monday.replace(microsecond=0),
            'end_datetime': (self.reference_monday + timedelta(hours=1)).replace(microsecond=0),
            'allday': False,
        }, {
            'start_datetime': (self.reference_monday + timedelta(days=1)).replace(microsecond=0),
            'end_datetime': (self.reference_monday + timedelta(days=2)).replace(microsecond=0),
            'allday': True,
        }]
        apt_type = self.env['calendar.appointment.type'].create({
            'category': 'custom',
            'name': 'Custom with unique slots',
            'slot_ids': [(5, 0)] + [
                (0, 0, {'allday': slot['allday'],
                        'end_datetime': slot['end_datetime'],
                        'slot_type': 'unique',
                        'start_datetime': slot['start_datetime'],
                       }
                ) for slot in unique_slots
            ],
        })
        self.assertEqual(apt_type.category, 'custom', "It should be a custom appointment type")
        self.assertEqual(apt_type.employee_ids, self.apt_manager_employee)
        self.assertEqual(len(apt_type.slot_ids), 2, "Two slots should have been assigned to the appointment type")

        with freeze_time(self.reference_now):
            slots = apt_type._get_appointment_slots('Europe/Brussels')

        global_slots_startdate = self.reference_now_monthweekstart
        global_slots_enddate = date(2022, 3, 6)  # last day of last week of February
        self.assertSlots(
            slots,
            [{'name_formated': 'February 2022',
              'month_date': datetime(2022, 2, 1),
              'weeks_count': 5,  # 31/01 -> 28/02 (06/03)
             }
            ],
            {'enddate': global_slots_enddate,
             'startdate': global_slots_startdate,
             'slots_day_specific': {
                self.reference_monday.date(): [{'end': 9, 'start': 8}],  # first unique 1 hour long
                (self.reference_monday + timedelta(days=1)).date(): [{'allday': True, 'end': False, 'start': 8}],  # second unique all day-based
             },
             'slots_start_hours': [],  # all slots in this tests are unique, other dates have no slots
             'slots_startdate': self.reference_monday.date(),  # first Monday after reference_now
             'slots_weekdays_nowork': range(2, 7)  # working hours only on Monday/Tuesday (0, 1)
            }
        )

    @users('staff_user_aust')
    def test_timezone_delta(self):
        """ Test timezone delta. Not sure what original test was really doing. """
        # As if the second user called the function
        apt_type = self.apt_type_bxls_2days.with_user(self.env.user).with_context(
            lang='en_US',
            tz=self.staff_user_aust.tz,
            uid=self.staff_user_aust.id,
        )

        # Do what the controller actually does, aka sudo
        with freeze_time(self.reference_now):
            slots = apt_type.sudo()._get_appointment_slots('Australia/West', employee=None)

        global_slots_startdate = self.reference_now_monthweekstart
        global_slots_enddate = date(2022, 4, 3)  # last day of last week of March
        self.assertSlots(
            slots,
            [{'name_formated': 'February 2022',
              'month_date': datetime(2022, 2, 1),
              'weeks_count': 5,  # 31/01 -> 28/02 (06/03)
             },
             {'name_formated': 'March 2022',
              'month_date': datetime(2022, 3, 1),
              'weeks_count': 5,  # 28/02 -> 28/03 (03/04)
             }
            ],
            {'enddate': global_slots_enddate,
             'startdate': global_slots_startdate,
             'slots_enddate': self.reference_now.date() + timedelta(days=15),  # maximum 2 weeks of slots
             'slots_start_hours': [15, 16, 17, 18, 20],  # based on appointment type start hours of slots but 12 is pause midi, set in UTC+8
             'slots_startdate': self.reference_monday.date(),  # first Monday after reference_now
             'slots_weekdays_nowork': range(2, 7)  # working hours only on Monday/Tuesday (0, 1)
            }
        )

    @users('apt_manager')
    def test_unique_slots_availabilities(self):
        """ Check that the availability of each unique slot is correct.
        First we test that the 2 unique slots of the custom appointment type
        are available. Then we check that there is now only 1 availability left
        after the creation of a meeting which encompasses a slot. """
        reference_monday = self.reference_monday.replace(microsecond=0)
        unique_slots = [{
            'allday': False,
            'end_datetime': reference_monday + timedelta(hours=1),
            'start_datetime': reference_monday,
        }, {
            'allday': False,
            'end_datetime': reference_monday + timedelta(hours=3),
            'start_datetime': reference_monday + timedelta(hours=2),
        }]
        apt_type = self.env['calendar.appointment.type'].create({
            'category': 'custom',
            'name': 'Custom with unique slots',
            'slot_ids': [(0, 0, {
                'allday': slot['allday'],
                'end_datetime': slot['end_datetime'],
                'slot_type': 'unique',
                'start_datetime': slot['start_datetime'],
                }) for slot in unique_slots
            ],
        })

        with freeze_time(self.reference_now):
            slots = apt_type._get_appointment_slots('UTC')
        # get all monday slots where apt_manager is available
        available_unique_slots = self._filter_appointment_slots(
            slots,
            filter_months=[(2, 2022)],
            filter_weekdays=[0],
            filter_employees=self.apt_manager_employee)
        self.assertEqual(len(available_unique_slots), 2)

        # Create a meeting encompassing the first unique slot
        self._create_meetings(self.apt_manager, [(
            unique_slots[0]['start_datetime'],
            unique_slots[0]['end_datetime'],
            False,
        )])

        with freeze_time(self.reference_now):
            slots = apt_type._get_appointment_slots('UTC')
        available_unique_slots = self._filter_appointment_slots(
            slots,
            filter_months=[(2, 2022)],
            filter_weekdays=[0],
            filter_employees=self.apt_manager_employee)
        self.assertEqual(len(available_unique_slots), 1)
        self.assertEqual(
            available_unique_slots[0]['datetime'],
            unique_slots[1]['start_datetime'].strftime('%Y-%m-%d %H:%M:%S'),
        )

    def test_check_appointment_timezone(self):
        session = self.authenticate('demo', 'demo')
        odoo.http.root.session_store.save(session)
        appointment = self.apt_type_bxls_2days
        appointment_url = url_join(appointment.get_base_url(), '/calendar/%s' % slug(appointment))
        appointment_info_url = "%s/info?" % appointment_url
        url_inside_of_slot = appointment_info_url + url_encode({
            'employee_id': self.staff_employee_bxls.id,
            'date_time': datetime(2023, 1, 9, 9, 0),  # 9/01/2023 is a Monday, there is a slot at 9:00
            'duration': 1,
        })
        # User should be able open url without timezone session
        self.url_open(url_inside_of_slot)

    @users('apt_manager')
    def test_multi_user_slot_availabilities(self):
        """ Check that when called with no / one / several employees, the
        methods computing the slots work as expected: if no employee is set, all employees
        of the appointment_type will be used. If one or more employees are set, they
        will be used to compute availabilities. However, if employee / all employees given
        as argument is not among the staff of the appointment type, return empty list."""
        reccuring_slots_utc = [{
            'weekday': '1',
            'start_hour': 6.0,  # Monday 06:00 -> 07:00 (-> falls in aust work hours range)
            'end_hour': 7.0,
        }, {
            'weekday': '2',
            'start_hour': 9.0,  # Tuesday 09:00 -> 11:00 (-> falls in bxls work hours range)
            'end_hour': 11.0,
        }]
        apt_type_UTC = self.env['calendar.appointment.type'].create({
            'appointment_tz': 'UTC',
            'assign_method': 'random',
            'category': 'website',
            'max_schedule_days': 5,  # Only consider the first three slots
            'name': 'Private Guitar Lesson',
            'slot_ids': [(0, False, {
                'weekday': slot['weekday'],
                'start_hour': slot['start_hour'],
                'end_hour': slot['end_hour'],
            }) for slot in reccuring_slots_utc],
            'employee_ids': [self.staff_employee_bxls.id, self.staff_employee_aust.id],
        })

        exterior_employee = self.apt_manager_employee

        with freeze_time(self.reference_now):
            slots_no_employee = apt_type_UTC._get_appointment_slots('UTC')
            slots_exterior_employee = apt_type_UTC._get_appointment_slots('UTC', exterior_employee)
            slots_employee_aust = apt_type_UTC._get_appointment_slots('UTC', self.staff_employee_aust)
            slots_employee_all = apt_type_UTC._get_appointment_slots('UTC', self.staff_employee_bxls | self.staff_employee_aust)
            slots_user_bxls_exterior_user = apt_type_UTC._get_appointment_slots('UTC', self.staff_employee_bxls | exterior_employee)

        self.assertTrue(len(self._filter_appointment_slots(slots_no_employee)) == 3)
        self.assertFalse(slots_exterior_employee)
        self.assertTrue(len(self._filter_appointment_slots(slots_employee_aust)) == 1)
        self.assertTrue(len(self._filter_appointment_slots(slots_employee_all)) == 3)
        self.assertTrue(len(self._filter_appointment_slots(slots_user_bxls_exterior_user)) == 2)
