import testtools
from schedules_tools import converter
from schedules_tools.models import Schedule
from schedules_tools.storage import StorageBase
#from scripts import schedule_converter as converter_cli
import tempfile
import os
import datetime
import mock
import pytest

DATA_DIR = 'data'

PARENT_DIRNAME = os.path.basename(os.path.dirname(os.path.realpath(__file__)))
BASE_DIR = os.path.dirname(os.path.realpath(
    os.path.join(__file__, os.pardir)))
CURR_DIR = os.path.join(BASE_DIR, PARENT_DIRNAME)


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
        conv_from = converter.ScheduleConverter()
        in_file = os.path.join(CURR_DIR, DATA_DIR, input_file)
        in_file = os.path.realpath(in_file)
        conv_from.import_schedule(in_file)

        conv_from.export_schedule(target_format=target_format,
                                  output=self.file_out_name)

        if not self.file_out_name.endswith(suffix):
            new_name = self.file_out_name + suffix
            os.rename(self.file_out_name, new_name)
            self.file_out_name = new_name

        conv_to = converter.ScheduleConverter()
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

    def test_init_storage_handler(self):
        handler_opt_args = {
            'source_storage_format': 'cvs'
        }
        handle = 'source.tjx'

        conv = converter.ScheduleConverter()
        assert conv.storage_handler is None

        conv._init_storage_handler(handle, handler_opt_args)
        inst_storage = conv.storage_handler

        assert isinstance(inst_storage, StorageBase)

        # try to reinitialize
        conv._init_storage_handler(handle, handler_opt_args)
        assert conv.storage_handler is inst_storage

    @mock.patch('schedules_tools.converter.ScheduleConverter.storage_handler',
                new_callable=mock.PropertyMock)
    @mock.patch.object(converter.ScheduleConverter, '_get_schedule_handler_cls')
    @mock.patch.object(converter.ScheduleConverter, '_get_handle_from_storage')
    def test_handle_modified_since_from_handle(self,
                                               mock_get_handle_from_storage,
                                               mock_get_schedule_handler_cls,
                                               mock_storage_handler):
        conv = converter.ScheduleConverter()
        handle = 'source.tjx'
        curr_date = datetime.datetime(2010, 3, 13)
        mock_storage_handler.return_value = None

        conv.handle_modified_since(handle, curr_date)

        mock_get_schedule_handler_cls.assert_called()
        mock_storage_handler.get_handle_mtime.assert_not_called()

    @mock.patch.object(converter.ScheduleConverter, 'storage_handler')
    @mock.patch.object(converter.ScheduleConverter, '_get_schedule_handler_cls')
    @mock.patch.object(converter.ScheduleConverter, '_get_handle_from_storage')
    def test_handle_modified_since_from_storage(self,
                                                mock_get_handle_from_storage,
                                                mock_get_schedule_handler_cls,
                                                mock_storage_handler):
        handle = 'source.tjx'
        date_mtime_newer = datetime.datetime(2011, 3, 13)
        date_mtime_older = datetime.datetime(2009, 3, 13)
        date_storage_handler = datetime.datetime(2010, 3, 13)

        mock_provide_mtime = mock.PropertyMock()
        mock_provide_mtime.return_value = True
        mock_storage_handler.get_handle_mtime.return_value = date_storage_handler
        type(mock_storage_handler).provide_mtime = mock_provide_mtime

        conv = converter.ScheduleConverter()
        assert conv.handle_modified_since(handle, date_mtime_older)

        mock_storage_handler.get_handle_mtime.assert_called()

        assert not conv.handle_modified_since(handle, date_mtime_newer)

    @mock.patch.object(converter.ScheduleConverter, 'storage_handler')
    @mock.patch.object(converter.ScheduleConverter, '_get_schedule_handler_cls')
    @mock.patch.object(converter.ScheduleConverter, '_get_handle_from_storage')
    def test_import_schedule_with_storage_provides_mtime_changelog(
            self,
            mock_get_handle_from_storage,
            mock_get_schedule_handler_cls,
            mock_storage_handler):
        mock_schedule_handler_cls = mock.Mock()
        mock_schedule_handler = mock.Mock()
        provided_schedule = Schedule()
        date_mtime_storage = datetime.datetime(2009, 3, 13)
        provided_schedule.mtime = datetime.datetime(2019, 3, 13)

        mock_schedule_handler.import_schedule.return_value = provided_schedule
        type(mock_schedule_handler).provide_changelog = mock.PropertyMock(return_value=False)

        mock_schedule_handler_cls.return_value = mock_schedule_handler
        mock_get_schedule_handler_cls.return_value = mock_schedule_handler_cls

        mock_storage_handler.get_handle_mtime.return_value = date_mtime_storage
        type(mock_storage_handler).provide_mtime = mock.PropertyMock(return_value=True)

        mock_storage_handler.get_handle_changelog.return_value = 'storage-changelog'
        type(mock_storage_handler).provide_changelog = mock.PropertyMock(return_value=True)

        handle = 'source.tjx'

        conv = converter.ScheduleConverter()
        schedule = conv.import_schedule(handle)

        assert schedule is provided_schedule
        assert schedule.mtime == date_mtime_storage
        assert schedule.changelog == 'storage-changelog'
        mock_schedule_handler.get_handle_changelog.assert_not_called()
        mock_storage_handler.get_handle_changelog.assert_called()
        mock_storage_handler.get_handle_mtime.assert_called()

    @mock.patch.object(converter.ScheduleConverter, 'storage_handler')
    @mock.patch.object(converter.ScheduleConverter, '_get_schedule_handler_cls')
    @mock.patch.object(converter.ScheduleConverter, '_get_handle_from_storage')
    def test_import_schedule_schedule_handler_provides_changelog(
            self,
            mock_get_handle_from_storage,
            mock_get_schedule_handler_cls,
            mock_storage_handler):
        mock_schedule_handler_cls = mock.Mock()
        mock_schedule_handler = mock.Mock()
        provided_schedule = Schedule()
        date_mtime_storage = datetime.datetime(2009, 3, 13)
        provided_schedule.mtime = datetime.datetime(2019, 3, 13)

        mock_schedule_handler.import_schedule.return_value = provided_schedule
        type(mock_schedule_handler).provide_changelog = mock.PropertyMock(return_value=True)
        mock_schedule_handler.get_handle_changelog.return_value = 'sch-changelog'

        mock_schedule_handler_cls.return_value = mock_schedule_handler
        mock_get_schedule_handler_cls.return_value = mock_schedule_handler_cls

        mock_storage_handler.get_handle_mtime.return_value = date_mtime_storage
        type(mock_storage_handler).provide_mtime = mock.PropertyMock(return_value=True)

        mock_storage_handler.get_handle_changelog.return_value = 'storage-changelog'
        type(mock_storage_handler).provide_changelog = mock.PropertyMock(return_value=True)

        handle = 'source.tjx'

        conv = converter.ScheduleConverter()
        schedule = conv.import_schedule(handle)

        assert schedule is provided_schedule
        assert schedule.mtime == date_mtime_storage
        assert schedule.changelog == 'storage-changelog'
        mock_storage_handler.get_handle_changelog.assert_called()
        mock_storage_handler.get_handle_mtime.assert_called()

    @mock.patch.object(converter.ScheduleConverter, 'storage_handler')
    @mock.patch.object(converter.ScheduleConverter, '_get_schedule_handler_cls')
    @mock.patch.object(converter.ScheduleConverter, '_get_handle_from_storage')
    def test_import_schedule_storage_handler_overrides_schedule_changelog(
            self,
            mock_get_handle_from_storage,
            mock_get_schedule_handler_cls,
            mock_storage_handler):
        mock_schedule_handler_cls = mock.Mock()
        mock_schedule_handler = mock.Mock()
        provided_schedule = Schedule()
        date_mtime_storage = datetime.datetime(2009, 3, 13)
        provided_schedule.mtime = datetime.datetime(2010, 3, 13)

        mock_schedule_handler.import_schedule.return_value = provided_schedule
        type(mock_schedule_handler).provide_changelog = mock.PropertyMock(return_value=True)
        mock_schedule_handler.get_handle_changelog.return_value = 'sch-changelog'

        mock_schedule_handler_cls.return_value = mock_schedule_handler
        mock_get_schedule_handler_cls.return_value = mock_schedule_handler_cls

        type(mock_storage_handler).provide_mtime = mock.PropertyMock(return_value=False)

        mock_storage_handler.get_handle_changelog.return_value = 'storage-changelog'
        type(mock_storage_handler).provide_changelog = mock.PropertyMock(return_value=True)

        handle = 'source.tjx'
        conv = converter.ScheduleConverter()
        schedule = conv.import_schedule(handle)

        assert schedule is provided_schedule
        assert schedule.changelog == 'storage-changelog'
        mock_storage_handler.get_handle_changelog.assert_called()
        mock_storage_handler.get_handle_mtime.assert_not_called()

    @mock.patch.object(converter.ScheduleConverter, 'storage_handler')
    def test_get_local_handle_first_time(self, mock_storage_handler):
        mock_storage_handler.get_local_handle.return_value = 'local-handle'

        conv = converter.ScheduleConverter()
        assert conv._get_local_handle() == 'local-handle'
        mock_storage_handler.get_local_handle.assert_called()

    @mock.patch.object(converter.ScheduleConverter, 'storage_handler')
    def test_get_local_handle_several_times(self, mock_storage_handler):
        mock_storage_handler.get_local_handle.return_value = 'local-handle'

        conv = converter.ScheduleConverter()
        assert conv._get_local_handle() == 'local-handle'
        assert conv._get_local_handle() == 'local-handle'
        assert conv._get_local_handle() == 'local-handle'
        assert conv._get_local_handle() == 'local-handle'

        mock_storage_handler.get_local_handle.assert_called()
        mock_storage_handler.get_local_handle.call_count == 1

    @mock.patch.object(converter.ScheduleConverter, 'local_handle')
    @mock.patch.object(converter.ScheduleConverter, 'storage_handler')
    def test_cleanup_local_handle(
            self,
            mock_storage_handle,
            mock_local_handle):
        conv = converter.ScheduleConverter()
        conv.cleanup_local_handle()

        mock_storage_handle.clean_local_handle.assert_called()

    @mock.patch.object(converter.ScheduleConverter, 'local_handle')
    @mock.patch('schedules_tools.converter.ScheduleConverter.storage_handler',
                new_callable=mock.PropertyMock)
    def test_cleanup_local_handle_without_storage(
            self,
            mock_storage_handle,
            mock_local_handle):
        mock_storage_handle.return_value = None
        conv = converter.ScheduleConverter()
        conv.cleanup_local_handle()

        mock_storage_handle.clean_local_handle.assert_not_called()

    @mock.patch('schedules_tools.converter.ScheduleConverter.local_handle',
                new_callable=mock.PropertyMock)
    @mock.patch.object(converter.ScheduleConverter, 'storage_handler')
    def test_cleanup_local_handle_without_local_handle(
            self,
            mock_storage_handle,
            mock_local_handle):
        mock_local_handle.return_value = None
        conv = converter.ScheduleConverter()
        conv.cleanup_local_handle()

        mock_storage_handle.clean_local_handle.assert_not_called()


#class TestConverterCLI(BaseTestConvert):
#    def test_discover_handlers(self):
#        args = ['--handlers-path', 'tests/foohandlers',
#                self.file_tjx, 'abc', self.file_out_name]
#        converter_cli.main(args)
#        with open(self.file_out_name) as fd:
#            line = fd.readline()
#            assert line == self.schedule_name
#
#    def test_override_handlers(self):
#        args = ['--handlers-path', 'tests/conflicthandlers',
#                self.file_tjx2, 'tjx', self.file_out_name]
#        converter_cli.main(args)
#        with open(self.file_out_name) as fd:
#            line = fd.readline()
#            assert line == 'schedule.name={}'.format(self.schedule_name)
#
#    def test_tjx_msp(self):
#        args = [self.file_tjx, 'msp', self.file_out_name]
#        converter_cli.main(args)
