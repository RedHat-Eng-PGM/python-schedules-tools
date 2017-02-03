from testtools import TestCase
from schedules_tools.handlers import msp, tjx, tjx2
from schedules_tools import models
from lxml import etree
from tests import create_test_schedule


class TestHandlers(TestCase):
    def setUp(self):
        super(TestHandlers, self).setUp()

    def tearDown(self):
        super(TestHandlers, self).tearDown()

    def test_tjx(self):
        pass

    def test_tjx2(self):
        pass

    def test_msp(self):
        pass

    def test_msp_parse_ext_attr(self):
        sch = models.Schedule()
        handle = msp.ScheduleHandler_msp(sch)
        etree.Element('Value').text = 'neco'
        handle._parse_extended_attr()
        pass
