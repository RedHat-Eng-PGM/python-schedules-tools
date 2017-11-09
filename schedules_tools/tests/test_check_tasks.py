import pytest
import os

from schedules_tools import converter


DATA_DIR = 'data'
# tests
PARENT_DIRNAME = os.path.basename(os.path.dirname(os.path.realpath(__file__)))

# schedules_tools
BASE_DIR = os.path.dirname(os.path.realpath(
    os.path.join(__file__, os.pardir)))

# schedules_tools/tests
CURR_DIR = os.path.join(BASE_DIR, PARENT_DIRNAME)


class CheckTaskExistence(object):
    schedule = None

    @pytest.fixture(autouse=True)
    def setUp(self):
        super(CheckTaskExistence, self).setUp()
        input_schedule = os.path.join(CURR_DIR, DATA_DIR, 'input.tjx')
        conv = converter.ScheduleConverter()
        self.schedule = conv.import_schedule(input_schedule)

    def test_empty_check_list(self):
        check_tasks = dict()
        missing_tasks = self.schedule.check_for_taskname(check_tasks)
        assert len(missing_tasks) == 0

    def test_exact_match(self):
        # key = task name, value = match from beginning
        check_tasks = {
            'Release': False,
            'Test 2': False,
        }
        missing_tasks = self.schedule.check_for_taskname(check_tasks)
        assert len(missing_tasks) == 0

    def test_exact_not_match(self):
        # key = task name, value = match from beginning
        check_tasks = {
            'Releaseeee': False,
            'Test 2': False,
        }
        missing_tasks = self.schedule.check_for_taskname(check_tasks)
        assert len(missing_tasks) == 1
        assert 'Releaseeee' in missing_tasks

    def test_startswith_match(self):
        check_tasks = {
            'Devel': True,  # Should match 'Development'
            'T': True,  # Should match 'Test 1', 'Testing phase', ...
        }
        missing_tasks = self.schedule.check_for_taskname(check_tasks)
        assert len(missing_tasks) == 0

    def test_startswith_not_match(self):
        check_tasks = {
            'Developing something completely different': True,
            'Tradada': True,
        }
        missing_tasks = self.schedule.check_for_taskname(check_tasks)

        assert len(missing_tasks) == 2
        assert 'Developing something completely different' in missing_tasks
        assert 'Tradada' in missing_tasks

    def test_combine_exact_startswith_match(self):
        check_tasks = {
            'Release': False,
            'Test': True
        }
        missing_tasks = self.schedule.check_for_taskname(check_tasks)
        assert len(missing_tasks) == 0

    def test_combine_exact_startswith_not_matchs(self):
        check_tasks = {
            'Releaseeee': False,
            'Release': False,
            'Test': True,
            'Testnothing': True
        }
        missing_tasks = self.schedule.check_for_taskname(check_tasks)
        assert len(missing_tasks) == 2
        assert 'Releaseeee' in missing_tasks
        assert 'Testnothing' in missing_tasks
