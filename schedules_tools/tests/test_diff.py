import datetime
import pytest

from schedules_tools.tests import create_test_schedule


class TestDiff(object):
    sch1 = None
    sch2 = None

    @pytest.fixture(autouse=True)
    def setUp(self):
        self.sch1 = create_test_schedule()
        self.sch2 = create_test_schedule()

    def test_identical(self):
        diff = self.sch1.diff(self.sch2)

        assert diff == ''

    def test_sch_attrs(self):
        self.sch1.name = '_test_value 1.0.42'
        self.sch1.used_flags = set(['flag1', 'qe'])
        self.sch1.dStart = datetime.datetime(1970, 1, 1)
        self.sch1.dFinish = datetime.datetime(4970, 1, 1)
        self.sch2.changelog['today'] = 'change'

        diff = self.sch1.diff(self.sch2)

        assert diff != ''
        assert 'name' in diff
        assert 'used_flags' in diff
        assert 'dStart' in diff
        assert 'dFinish' in diff
        assert 'changelog' in diff

    def test_task_attrs(self):
        date_delta = datetime.timedelta(1)

        task = self.sch1.tasks[0].tasks[0]
        task.dStart -= date_delta
        task.dFinish += date_delta
        task.link = 'nothing'
        task.note = 'note123'

        diff = self.sch1.diff(self.sch2)

        assert 'link' in diff
        assert 'dStart' in diff
        assert 'dFinish' in diff
        assert 'note' in diff

    def test_missing_task(self):
        diff = self.sch1.diff(self.sch2)
        assert diff == ''

        self.sch2.tasks[0].tasks.pop()

        diff = self.sch1.diff(self.sch2)
        assert diff != ''

    def test_whole_days(self):
        time_delta = datetime.timedelta(minutes=1)
        self.sch2.tasks[0].tasks[1].tasks[0].dFinish -= time_delta

        diff = self.sch1.diff(self.sch2, whole_days=True)
        assert diff == ''


class TestDiffCLI(object):
    pass