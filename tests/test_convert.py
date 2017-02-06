import testtools
from schedules_tools import schedule_converter
import tempfile
import os

DATA_DIR = 'data'

CURR_DIR = os.path.basename(os.path.dirname(os.path.realpath(__file__)))
print CURR_DIR


class BaseTestConvert(testtools.TestCase):
    _filenames = {
        'tjx': 'proj-10-1-2.tjx',
        'tjx2': 'proj-10-1-2-v2.tjx',
        'smartsheet': 'proj-10-1-2-smartsheet.xml'
    }
    file_tjx = ''
    file_tjx2 = ''
    file_smartsheet = ''
    schedule_name = 'Test project 10'

    file_out_fd = None
    file_out_name = None

    def setUp(self):
        super(BaseTestConvert, self).setUp()
        self.file_out_fd, self.file_out_name = tempfile.mkstemp()

        # prepend data dir to real path of files
        for k, v in self._filenames.items():
            key = 'file_{}'.format(k)
            val = os.path.join(CURR_DIR, DATA_DIR, v)
            val = os.path.realpath(val)
            setattr(self, key, val)

    def tearDown(self):
        super(BaseTestConvert, self).tearDown()
        os.remove(self.file_out_name)


class TestConverter(BaseTestConvert):
    def _test_format_combination(self, input_file, target_format, suffix):
        """
        Do import of input_file, export it into target_format and compare
        these two files/handles, if there are some differences (shouldn't be).

        Args:
            input_file: Source handle/file with schedule
            target_format: Desired export format
            suffix: Target file suffix (i.e. '.tjx')
        """
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


class TestConverterCLI(BaseTestConvert):
    def test_discover_handlers(self):
        args = ['--handlers-path', 'tests/foohandlers',
                self.file_tjx, 'abc', self.file_out_name]
        schedule_converter.main(args)
        with open(self.file_out_name) as fd:
            line = fd.readline()
            assert line == self.schedule_name

    def test_override_handlers(self):
        args = ['--handlers-path', 'tests/conflicthandlers',
                self.file_tjx2, 'tjx', self.file_out_name]
        schedule_converter.main(args)
        with open(self.file_out_name) as fd:
            line = fd.readline()
            assert line == 'schedule.name={}'.format(self.schedule_name)

    def test_tjx_msp(self):
        args = [self.file_tjx, 'msp', self.file_out_name]
        schedule_converter.main(args)
