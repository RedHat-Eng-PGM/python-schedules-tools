from schedules_tools import converter
from schedules_tools.models import Schedule
from schedules_tools.storage_handlers import StorageBase
#from scripts import schedule_converter as converter_cli
import tempfile
import os
import datetime
import mock
import pytest

DATA_DIR = 'schedule_files'

PARENT_DIRNAME = os.path.basename(os.path.dirname(os.path.realpath(__file__)))
BASE_DIR = os.path.dirname(os.path.realpath(
    os.path.join(__file__, os.pardir)))
CURR_DIR = os.path.join(BASE_DIR, PARENT_DIRNAME)


class BaseTestConvert(object):
    _filenames = {
        'tjx': 'proj-10-1-2.tjx',
        'tjx2': 'proj-10-1-2-v2.tjx',
        'smartsheet': 'import-schedule-msp.xml'
    }
    file_tjx = ''
    file_tjx2 = ''
    file_smartsheet = ''
    schedule_name = 'Test project 10'

    file_out_fd = None
    file_out_name = None

    @pytest.fixture(autouse=True)
    def setUp(self):
        self.file_out_fd, self.file_out_name = tempfile.mkstemp()

        # prepend data dir to real path of files
        for k, v in self._filenames.items():
            key = 'file_{}'.format(k)
            val = os.path.join(CURR_DIR, DATA_DIR, v)
            val = os.path.realpath(val)
            setattr(self, key, val)
        yield
        os.remove(self.file_out_name)


class TestConverter(BaseTestConvert):

    def test_init_storage_handler(self):
        handle = 'source.tjx'

        conv = converter.ScheduleConverter()
        assert conv.storage_handler is None

        conv._init_storage_handler(handle, storage_src_format='cvs')
        inst_storage = conv.storage_handler

        assert isinstance(inst_storage, StorageBase)

        # try to reinitialize
        conv._init_storage_handler(handle, storage_src_format='cvs')
        assert conv.storage_handler is inst_storage

    @mock.patch('schedules_tools.converter.ScheduleConverter.storage_handler',
                new_callable=mock.PropertyMock)
    @mock.patch.object(converter.ScheduleConverter, '_get_schedule_handler_cls')
    @mock.patch.object(converter.ScheduleConverter, '_get_local_handle_from_storage')
    def test_handle_modified_since_from_handle(self,
                                               mock_get_local_handle_from_storage,
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
    @mock.patch.object(converter.ScheduleConverter, '_get_local_handle_from_storage')
    def test_handle_modified_since_from_storage(self,
                                                mock_get_local_handle_from_storage,
                                                mock_get_schedule_handler_cls,
                                                mock_storage_handler):
        handle = 'source.tjx'
        date_storage_handler = datetime.datetime(2010, 3, 13)

        mock_provide_mtime = mock.PropertyMock()
        mock_provide_mtime.return_value = True
        mock_storage_handler.get_handle_mtime.return_value = date_storage_handler
        type(mock_storage_handler).provide_mtime = mock_provide_mtime

        conv = converter.ScheduleConverter()
        conv.handle_modified_since(handle, date_storage_handler)
        mock_storage_handler.handle_modified_since.assert_called()

    @mock.patch.object(converter.ScheduleConverter, 'storage_handler')
    @mock.patch.object(converter.ScheduleConverter, '_get_schedule_handler_cls')
    @mock.patch.object(converter.ScheduleConverter, '_get_local_handle_from_storage')
    def test_import_schedule_with_storage_provides_mtime_changelog(
            self,
            mock_get_local_handle_from_storage,
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
    @mock.patch.object(converter.ScheduleConverter, '_get_local_handle_from_storage')
    def test_import_schedule_schedule_handler_provides_changelog(
            self,
            mock_get_local_handle_from_storage,
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
    @mock.patch.object(converter.ScheduleConverter, '_get_local_handle_from_storage')
    def test_import_schedule_storage_handler_overrides_schedule_changelog(
            self,
            mock_get_local_handle_from_storage,
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
    def test_cleanup_local_handle(
            self,
            mock_storage_handle):
        conv = converter.ScheduleConverter()
        conv.cleanup_local_handle()

        mock_storage_handle.clean_local_handle.assert_called()

    @mock.patch('schedules_tools.converter.ScheduleConverter.storage_handler',
                new_callable=mock.PropertyMock)
    def test_cleanup_local_handle_without_storage(
            self,
            mock_storage_handle):
        mock_storage_handle.return_value = None
        conv = converter.ScheduleConverter()
        conv.cleanup_local_handle()

        mock_storage_handle.clean_local_handle.assert_not_called()

    def test_msp_parse_flags_note_url(self):
        conv = converter.ScheduleConverter()
        schedule = conv.import_schedule(self.file_smartsheet)

        # Test1 - Testing Phase task
        assert ['flag1'] == schedule.tasks[0].tasks[0].tasks[2].flags

        # Test2 - Another task
        assert ['flag1', 'flag2', 'flag3'] == schedule.tasks[0].tasks[1].tasks[1].flags

        # Test2 - Another task
        assert 'test2 note' == schedule.tasks[0].tasks[1].tasks[1].note

        # Test1 - Development
        assert 'https://github.com/1' == schedule.tasks[0].tasks[0].tasks[0].link


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
