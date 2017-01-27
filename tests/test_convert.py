import testtools
from schedules_tools import schedule_converter
import tempfile
import os

DATA_DIR = 'data'

CURR_DIR = os.path.basename(os.path.dirname(os.path.realpath(__file__)))
print CURR_DIR


class TestConvert(testtools.TestCase):
    file_tjx = 'schedule.tjx'
    file_tjx2 = 'schedule-v2.tjx'
    file_smartsheet = 'smartsheet.xml'
    file_out_fd = None
    file_out_name = None

    def setUp(self):
        super(TestConvert, self).setUp()
        self.file_out_fd, self.file_out_name = tempfile.mkstemp()

    def tearDown(self):
        super(TestConvert, self).tearDown()
        os.remove(self.file_out_name)

    def _test_format_combination(self, input_file, target_format, suffix):
        conv_from = schedule_converter.ScheduleConverter()
        in_file = os.path.join(CURR_DIR, DATA_DIR, input_file)
        in_file = os.path.realpath(in_file)
        conv_from.import_schedule(in_file)

        conv_from.export_handle(target_format=target_format,
                                out_file=self.file_out_name)

        if not self.file_out_name.endswith(suffix):
            new_name = self.file_out_name + suffix
            os.rename(self.file_out_name, new_name)
            self.file_out_name = new_name

        conv_to = schedule_converter.ScheduleConverter()
        conv_to.import_schedule(self.file_out_name)

        diff = conv_from.schedule.diff(conv_to.schedule)
        assert diff == ''

    def test_tjx_txj(self):
        self._test_format_combination(self.file_tjx, 'tjx', '.tjx')

    def test_tjx2_txj(self):
        self._test_format_combination(self.file_tjx2, 'tjx', '.tjx')

    def test_tjx_smartsheet(self):
        self._test_format_combination(self.file_tjx, 'msp', '.xml')

    def test_smartsheet_smartsheet(self):
        self._test_format_combination(self.file_smartsheet, 'msp', '.xml')

    def test_smartsheet_tjx(self):
        self._test_format_combination(self.file_smartsheet, 'tjx', '.tjx')
