import datetime
import json
import pytest
import os

from schedules_tools.tests import create_test_schedule
from schedules_tools.converter import ScheduleConverter
from schedules_tools.diff import ScheduleDiff

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


class TestScheduleDiff(object):
    ref_sched = 'sched_diff_reference.xml'

    SCHEDS_DIR = os.path.join(BASE_DIR, 'schedule_files/schedule_diff')
    OUTPUT_FILES_DIR = os.path.join(BASE_DIR, 'fixtures/schedule_diff')

    diff_test_scenarios = (
        ('sched_diff_dates_changed', False, False),
        ('sched_diff_subtask_added', False, False),
        ('sched_diff_subtask_removed', False, False),
        ('sched_diff_subtask_removed', True, False),
        ('sched_diff_subtask_tree_added', False, False),
        ('sched_diff_subtask_tree_removed', False, False),
        ('sched_diff_task_appended', False, False),
        ('sched_diff_task_appended', True, False),
        ('sched_diff_tasks_renamed', False, False),
        ('sched_diff_time_changed', False, False),
        ('sched_diff_time_changed', True, False),
        ('sched_diff_reference', True, True),
        ('sched_diff_flags_changed', True, True),
        ('sched_diff_flags_changed', True, False),
    )

    def import_schedule(self, filename):
        path = os.path.join(self.SCHEDS_DIR, filename)
        conv = ScheduleConverter()
        return conv.import_schedule(path)

    @pytest.mark.parametrize(
        'schedule_name,trim_time,compare_flags',
        diff_test_scenarios
    )
    @pytest.mark.parametrize(
        'output_format',
        ['json', 'txt']
    )
    def test_diff(self, schedule_name, trim_time, compare_flags, output_format):

        left = self.import_schedule(self.ref_sched)
        right = self.import_schedule('%s.xml' % schedule_name)

        if compare_flags:
            extra_compare_attributes = ['flags']
        else:
            extra_compare_attributes = None

        diff = ScheduleDiff(
            left,
            right,
            trim_time=trim_time,
            extra_compare_attributes=extra_compare_attributes
        )

        if output_format == 'json':
            diff_output = diff.dump_json(indent=4)
        elif output_format == 'txt':
            diff_output = str(diff)
        else:
            raise ValueError

        diff_reference_filename = '%s%s%s.%s' % (
            schedule_name,
            '_trim_time' if trim_time else '',
            '_compare_flags' if compare_flags else '',
            output_format
        )

        regenerate = os.environ.get('REGENERATE', 'false').lower() == 'true'
        if regenerate:
            file_mode = 'w'
        else:
            file_mode = 'r'

        with open(
            os.path.join(self.OUTPUT_FILES_DIR, diff_reference_filename),
            file_mode
        ) as f:
            if regenerate:
                f.write(diff_output)
            else:
                expected_diff_output = f.read()

                if output_format == 'json':
                    # Need to load them again:
                    # 1) Dates are saved as strings in expected
                    # 2) Dict equality doesn't depend on keys order
                    expected_diff_output = json.loads(expected_diff_output)
                    diff_output = json.loads(diff_output)

                assert diff_output == expected_diff_output


class TestDiffCLI(object):
    pass
