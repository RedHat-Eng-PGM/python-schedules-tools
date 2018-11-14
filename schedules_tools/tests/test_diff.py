import datetime
import pytest
import os
import jsondate

from schedules_tools.tests import create_test_schedule
from schedules_tools.converter import ScheduleConverter
from schedules_tools.diff_v2 import ScheduleDiff

BASE_DIR = os.path.dirname(os.path.realpath(__file__))


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


def scheds_list(scheds_dir, ref_sched):
    return [f for f in os.listdir(scheds_dir) if f != ref_sched]


class TestScheduleDiff(object):
    ref_sched = 'sched_diff_reference.xml'

    SCHEDS_DIR = os.path.join(BASE_DIR, 'schedule_files/schedule_diff')
    OUTPUT_FILES_DIR = os.path.join(BASE_DIR, 'fixtures/schedule_diff')

    def import_schedule(self, filename):
        path = os.path.join(self.SCHEDS_DIR, filename)
        conv = ScheduleConverter()
        return conv.import_schedule(path)

    @pytest.fixture(params=scheds_list(scheds_dir=SCHEDS_DIR, 
                                       ref_sched=ref_sched), scope='class')
    def diff_res(self, request):
        filename = request.param

        left = self.import_schedule(self.ref_sched)
        right = self.import_schedule(filename)

        return ScheduleDiff(left, right), filename

    @pytest.fixture
    def expected(self, request, diff_res):
        name = os.path.splitext(diff_res[1])[0]
        ext = request.param

        with open(os.path.join(self.OUTPUT_FILES_DIR, '.'.join([name, ext]))) as f:
            yield f

    @pytest.mark.parametrize('expected', ['txt'], indirect=True)
    def test_txt_output(self, diff_res, expected):
        assert str(diff_res[0]) == expected.read()

    @pytest.mark.parametrize('expected', ['json'], indirect=True)
    def test_json_output(self, diff_res, expected):
        diff_json = diff_res[0].dump_json()
        assert jsondate.loads(diff_json) == jsondate.load(expected)


class TestDiffCLI(object):
    pass
