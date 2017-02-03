from testtools import TestCase
from schedules_tools import models


class TestModel(TestCase):
    def test_schedule_override_version(self):
        sch = models.Schedule()
        assert sch.version == ''
        sch.override_version('TJID', '1', '', '3')
        assert sch.version == ''
        sch.override_version('TJID', '1')
        assert sch.version == ''
        sch.override_version('TJID', '', '2', '3')
        assert sch.version == ''
        sch.override_version('TJID', '1', '2', '3')
        assert sch.version == '1.2.3'
