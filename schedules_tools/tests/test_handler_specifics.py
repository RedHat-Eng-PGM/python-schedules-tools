from testtools import TestCase
from schedules_tools.handlers import msp
from schedules_tools import models
from lxml import etree
import logging

logging.basicConfig()


class TestUnit_msp_parseExtAttrs(TestCase):
    schedule = None
    task = None
    handle = None
    element = None

    def setUp(self):
        super(TestUnit_msp_parseExtAttrs, self).setUp()

    def _prepare_inject_value(self):
        self.schedule = models.Schedule()
        self.task = models.Task(schedule=self.schedule)
        self.handle = msp.ScheduleHandler_msp(schedule=self.schedule)
        self.element = etree.Element('Value')

    def _inject_value(self, value):
        self.element.text = value
        self.handle._parse_extended_attr(self.task, self.element)

    def test_link(self):
        url = 'http://www.somewhere.io'
        valid_patterns = [
            'link: {}',
            'Link: {}',
            'Link:{}',
            'Link :{}',
            'link:{}',
            'Link:         {}',
            'Link:\n {}',
            '   Link:\t {} ',
            '   link\n:\t {} ',
        ]

        invalid_patterns = [
            '{}',       # missing prefix 'Link: '
            'link {}',  # missing ':'
        ]

        for pattern in valid_patterns:
            self._prepare_inject_value()
            self._inject_value(pattern.format(url))
            assert self.task.link == url

        for pattern in invalid_patterns:
            self._prepare_inject_value()
            self._inject_value(pattern.format(url))
            assert self.task.link != url

    def test_note(self):
        note = 'Very important text'
        valid_patterns = [
            'note: {}',
            'Note: {}',
            'Note:{}',
            'Note :{}',
            'note:{}',
            'Note:         {}',
            'Note:\n {}',
            '   Note:\t {} ',
            '   note\n:\t {} ',
        ]

        invalid_patterns = [
            '{}',
        ]

        for pattern in valid_patterns:
            self._prepare_inject_value()
            self._inject_value(pattern.format(note))
            assert self.task.note == note

        for pattern in invalid_patterns:
            self._prepare_inject_value()
            self._inject_value(pattern.format(note))
            assert self.task.note != note

    def test_flags(self):
        flags = set(['qe', 'pm', 'dev'])

        valid_patterns = [
            'flags: qe, pm, dev',
            'Flags: qe pm dev',
            'Flags:dev , pm , qe',
            'FLAgs : qe, pm dev',
            'flags:QE, PM, DEV',
            'Flags:\n qe, pm, dev',
            '   FLags:\t qe,\n pm, \tdev ',
            '  flags\n:\t dev PM qe, ',
        ]

        invalid_patterns = [
            'flag: qe pm dev',      # missing 's' in 'flags'
            'flags qe, pm, devel',  # missing ':'
        ]

        invalid_patterns_schedule = [
            'flags: qe; pm; dev',   # incorrect separator ';'
            'flags: qe, pm, devel'  # not expected value 'devel'
        ]

        for pattern in valid_patterns:
            self._prepare_inject_value()
            assert self.schedule.used_flags == set()
            self._inject_value(pattern)
            assert set(self.task.flags) == flags
            assert self.schedule.used_flags == flags

        for pattern in invalid_patterns:
            self._prepare_inject_value()
            assert self.schedule.used_flags == set()
            self._inject_value(pattern)
            assert set(self.task.flags) != flags
            assert self.schedule.used_flags == set()

        # flags will be parsed correctly, but their content wil not match
        # to reference
        for pattern in invalid_patterns_schedule:
            self._prepare_inject_value()
            assert self.schedule.used_flags == set()
            self._inject_value(pattern)
            assert set(self.task.flags) != flags
            assert self.schedule.used_flags != set()
