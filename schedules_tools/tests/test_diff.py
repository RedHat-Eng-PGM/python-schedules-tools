import datetime
import pytest
import os
import jsondate

from schedules_tools.tests import create_test_schedule
from schedules_tools.converter import ScheduleConverter
from schedules_tools.diff_v2 import ScheduleDiff

SCHEDS_DIRNAME = 'schedule_files'
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
SCHEDS_DIR = os.path.join(BASE_DIR, SCHEDS_DIRNAME)


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


class TestScheduleDiff(object):
    sched_files = ['schedule-diff-a.tjx', 'schedule-diff-b.tjx']

    test_data = [
        pytest.param(('diff_output.json', sched_files), id='json'),
        pytest.param(('diff_output.txt', sched_files), id='text')
    ]

    def import_schedule(self, filename):
        path = os.path.join(SCHEDS_DIR, filename)
        conv = ScheduleConverter()
        return conv.import_schedule(path)

    def diff(self, sched_a_file, sched_b_file):
        sched_a = self.import_schedule(sched_a_file)
        sched_b = self.import_schedule(sched_b_file)
        return ScheduleDiff(sched_a, sched_b)

    @pytest.fixture
    def diff_results(self, request):
        file, scheds_list = request.param
        diff = self.diff(*scheds_list)

        with open(os.path.join(BASE_DIR, 'fixtures', file)) as fd:
            f_ext = os.path.splitext(file)[1]
            if f_ext == '.json':
                yield jsondate.loads(diff.dump_json()), jsondate.load(fd)
            else:
                yield str(diff), fd.read()

    @pytest.mark.parametrize('diff_results', test_data, indirect=True)
    def test_equal_results(self, diff_results):
        actual, expected = diff_results
        assert actual == expected


class TestDiffCLI(object):
    pass
