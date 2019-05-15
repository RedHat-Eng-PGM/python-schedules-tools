from dateutil.tz import tzutc
import datetime
import json
import logging
import os
import pytest
import re
import shutil
from smartsheet import Smartsheet
from schedules_tools.schedule_handlers.smart_sheet import (
    SmartSheetExportException)


from schedules_tools.converter import ScheduleConverter
from schedules_tools.tests import jsondate
from schedules_tools.models import Schedule

# smartsheet log
logging.basicConfig(level=logging.INFO)

log = logging.getLogger(__name__)


def pytest_generate_tests(metafunc):
    source_function = metafunc.function.__name__

    if source_function == 'test_import':
        argnames = ['handler_name', 'import_schedule_file']
        argvalues = metafunc.cls.scenarios_import_combinations
        metafunc.parametrize(argnames, argvalues)
    elif source_function == 'test_export':
        argnames = ['handler_name', 'export_schedule_file', 'flat', 
                    'flag_show', 'flag_hide', 
                    'options', 'sort']
        argvalues = metafunc.cls.scenarios_export_combinations
        metafunc.parametrize(argnames, argvalues)


class TestHandlers(object):
    intermediary_reference_file = 'intermediary-struct-reference.json'
    schedule_files_dir = 'schedule_files'
    basedir = os.path.dirname(os.path.realpath(__file__))
    test_import_start_timestamp = None

    scenarios_import_combinations = [
        ('msp', 'import-schedule-msp.xml'),
        ('smartsheet', ''),
        ('json', 'import-schedule-json.json'),
        ('tjx2', 'import-schedule-tjx2.tjx'),
    ]
    scenarios_export_combinations = [
        ('msp', 'export-schedule-msp.xml', False, [], [], {}, None),
        ('json', 'export-schedule-json.json', False, [], [], {}, None),
        ('json', 'export-schedule-json-sort-name.json', False, [], [], {}, 'name'),
        ('json', 'export-schedule-json-sort-date.json', False, [], [], {}, 'dStart'),
        ('json', 'export-schedule-json.json-flags', False, ['flag1'], ['flag2'], {}, None),
        ('json', 'export-schedule-json-flat.json', True, [], [], {}, None),
        ('json', 'export-schedule-json-flat-sort-date.json', True, [], [], {}, 'dStart'),
        ('json', 'export-schedule-json-flat-flags.json', True, ['flag1'], ['flag2'], {}, None),
        ('ics', 'export-schedule-ics.ics', False, [], [], {}, None),
        ('html', 'export-schedule-html.html', False, [], [], {}, None),
        ('html', 'export-schedule-html-sort-date.html', False, [], [], {}, 'dStart'),
        ('html', 'export-schedule-html-options.html', False, [], [],
         dict(html_title='Test title', html_table_header='<p>Test header</p>'), None),
    ]

    smartsheet_columns_ids = ()
    smartsheet_sheet_id = None
    smartsheet_client = None
    replace_time_opts = dict(hour=0, minute=0, tzinfo=None)

    def _sanitize_export_test_ics(self, content):
        return re.sub('DTSTAMP:[0-9]+T[0-9]+Z', 'DTSTAMP:20170101T010101Z', content)

    def _clean_interm_struct(self, input_dict):
        """Removes keys that is not needed for comparison,
        unify time-part of dates"""
        keys_to_remove = ['unique_id_re', 'id_reg', 'ext_attr', 'flags_attr_id',
                          'resources', 'mtime']

        # remove schedule attrs
        for key in keys_to_remove:
            if key in input_dict:
                input_dict.pop(key)

        # Schedule attrs
        input_dict['dStart'] = input_dict['dStart'].replace(**self.replace_time_opts)
        input_dict['dFinish'] = input_dict['dFinish'].replace(**self.replace_time_opts)

        # Task(s) attrs
        for task in input_dict['tasks']:
            self._clear_task_time(task)

    def _clear_task_time(self, task):
        """For comparison purpose we ignore hours and minutes of task."""
        task['dStart'] = task['dStart'].replace(**self.replace_time_opts)
        task['dFinish'] = task['dFinish'].replace(**self.replace_time_opts)

        for inner_task in task['tasks']:
            self._clear_task_time(inner_task)

    @classmethod
    def _convert_struct_unicode_to_str(cls, data, ignore_dicts=False):
        # Taken from:
        # https://stackoverflow.com/questions/956867/how-to-get-string-objects-instead-of-unicode-from-json

        # if this is a unicode string, return its string representation
        if isinstance(data, unicode):
            return data.encode('utf-8')

        # if this is a list of values, return list of byteified values
        if isinstance(data, list):
            return [
                cls._convert_struct_unicode_to_str(item, ignore_dicts=True)
                for item in data
            ]

        # if this is a dictionary, return dictionary of byteified keys
        # and values but only if we haven't already byteified it
        if isinstance(data, dict) and not ignore_dicts:
            # decode datetime object separately
            data = jsondate._datetime_decoder(data)
            return {
                cls._convert_struct_unicode_to_str(key, ignore_dicts=True):
                    cls._convert_struct_unicode_to_str(value, ignore_dicts=True)
                for key, value in data.iteritems()
            }

        # if it's anything else, return it in its original form
        return data

    def get_intermediary_reference_schedule(self):
        interm_reference_file = os.path.join(self.basedir,
                                             self.intermediary_reference_file)

        with open(interm_reference_file) as fd:
            intermediary_input_dict = jsondate.load(
                fd, object_hook=self._convert_struct_unicode_to_str)

        schedule = Schedule.load_from_dict(intermediary_input_dict)
        return schedule

    def import_setup_handle_smartsheet(self):
        token = os.environ.get('SMARTSHEET_TOKEN', None)
        if not token:
            pytest.fail('You need to specify environment variable '
                        'SMARTSHEET_TOKEN to run smartsheet tests.')

        converter_options = {
            'smartsheet_token': token,
        }

        intermediary_input = self.get_intermediary_reference_schedule()

        conv = ScheduleConverter(intermediary_input)
        sheet_id = conv.export_schedule(output=None,
                                        target_format='smartsheet',
                                        options=converter_options)

        self._smartsheet_inject_extra_column(sheet_id, converter_options)

        return sheet_id, converter_options

    def _smartsheet_inject_extra_column(self, sheet_id, converter_options):
        """
        Add extra column with duplicated name. For testing only.

        Value of this extra column are shifted by 3 days into future from
        original.
        """
        client = Smartsheet(converter_options['smartsheet_token'])
        sheet = client.Sheets.get_sheet(sheet_id, page_size=None, page=None)

        start_column_id = None

        for column in sheet.columns:
            if column.title in ['Start', 'Start Date']:
                start_column_id = column.id
                break

        # Add intentionally another Start Date column - just for test purpose
        column_startdate_dup = client.models.Column({
            'title': 'Start Date',
            'type': 'DATE',
            'index': 11,
        })
        resp = client.Sheets.add_columns(sheet_id, column_startdate_dup)

        duplicated_column_id = resp.result[0].id

        if resp.message != 'SUCCESS':
            msg = 'Adding column failed: {}'.format(resp)
            raise SmartSheetExportException(msg, source=sheet_id)

        datetime_format = '%Y-%m-%dT%H:%M:%S'
        updated_rows = []
        for row in sheet.rows:
            original_cell_value = row.get_column(start_column_id).value
            new_value = datetime.datetime.strptime(original_cell_value,
                                                   datetime_format)
            new_value += datetime.timedelta(days=3)

            cell = client.models.Cell()
            cell.column_id = duplicated_column_id
            cell.value = new_value.strftime(datetime_format)

            new_row = client.models.Row()
            new_row.id = row.id
            new_row.cells.append(cell)
            updated_rows.append(new_row)

        resp = client.Sheets.update_rows(sheet_id, updated_rows)
        if resp.message != 'SUCCESS':
            msg = 'Inserting duplicated cells failed: {}'.format(resp)
            raise SmartSheetExportException(msg, source=sheet_id)

    def import_teardown_handle_smartsheet(self, handle, converter_options):
        client = Smartsheet(converter_options['smartsheet_token'])
        client.Sheets.delete_sheet(handle)

    def import_assert_changelog_smartsheet(self,
                                           reference_schedule_dict,
                                           imported_schedule_dict):
        changelog = imported_schedule_dict['changelog']
        assert len(changelog.keys()) == 1
        assert isinstance(changelog.keys()[0], int)

        record = changelog.values()[0]
        date_now = datetime.datetime.now(tz=tzutc())
        assert self.test_import_start_timestamp < record['date']
        assert record['date'] < date_now

    def test_import(self, handler_name, import_schedule_file):
        """
        Generic pytest fixture that provides arguments for import_schedule meth.
        If there is specified 'import_schedule_file' value of argument,
        its considered as filename of file-based handle.
        Otherwise will try to call 'fixture_import_handlename' method that
        provides these arguments (handle, options).
        Also it works as setup/teardown-like method of the handle's test
        (using yield within the 'fixture_import_' method).
        """
        handle = None
        converter_options = dict()
        self.test_import_start_timestamp = datetime.datetime.now(tz=tzutc())

        if import_schedule_file:
            handle = os.path.join(self.basedir, self.schedule_files_dir,
                                  import_schedule_file)
            converter_options = {
                'source_storage_format': 'local'
            }
        else:
            callback_name = 'import_setup_handle_' + handler_name
            if hasattr(self, callback_name):
                import_setup_fn = getattr(self, callback_name)
                handle, converter_options = import_setup_fn()

        try:
            conv = ScheduleConverter()
            schedule = conv.import_schedule(handle,
                                            schedule_src_format=handler_name,
                                            options=converter_options)
            assert 0 == len(schedule.errors_import)

            imported_schedule_dict = schedule.dump_as_dict()
            self._clean_interm_struct(imported_schedule_dict)

            interm_reference_file = os.path.join(
                self.basedir, self.intermediary_reference_file)
            regenerate = os.environ.get('REGENERATE', False) == 'true'
            if regenerate:
                log.info('test_import: Regenerating interm. reference file'
                         'from imported schedule.')

                with open(interm_reference_file, 'w+') as fd:
                    jsondate.dump(imported_schedule_dict,
                                  fd,
                                  sort_keys=True,
                                  indent=4,
                                  separators=(',', ': '))

            with open(interm_reference_file) as fd:
                reference_dict = json.load(
                    fd, object_hook=self._convert_struct_unicode_to_str)
            self._clean_interm_struct(reference_dict)

            # test/assert changelog separately, if there exists a hook
            callback_name = 'import_assert_changelog_' + handler_name
            if hasattr(self, callback_name):
                assert_changelog_fn = getattr(self, callback_name)
                assert_changelog_fn(reference_dict, imported_schedule_dict)

                # If asserting of changelog went well,
                # drop it from schedules dicts
                imported_schedule_dict.pop('changelog', None)
                reference_dict.pop('changelog', None)

            assert reference_dict == imported_schedule_dict

        finally:
            callback_name = 'import_teardown_handle_' + handler_name
            if not import_schedule_file and hasattr(self, callback_name):
                import_setup_fn = getattr(self, callback_name)
                import_setup_fn(handle, converter_options)

    def test_export(self, handler_name, export_schedule_file, 
                    flat, flag_show, flag_hide, options,
                    tmpdir, sort):
        full_export_schedule_file = os.path.join(self.basedir,
                                                 self.schedule_files_dir,
                                                 export_schedule_file)
        intermediary_input = self.get_intermediary_reference_schedule()
        export_output_file = tmpdir.join('exported_file')
        export_output_filename = str(export_output_file)

        conv = ScheduleConverter(intermediary_input)

        if flat:
            conv.schedule.make_flat()

        if sort:
            conv.schedule.sort_tasks(sort)

        conv.schedule.filter_flags(flag_show, flag_hide)

        conv.export_schedule(export_output_filename, handler_name,
                             options=options)
        actual_output = export_output_file.read()

        regenerate = os.environ.get('REGENERATE', False) == 'true'

        if regenerate:
            log.info('test_export: Regenerating exported file from '
                     'reference schedule.')
            shutil.copy(export_output_filename, full_export_schedule_file)

        with open(full_export_schedule_file) as fd:
            expected_output = fd.read()

        # sanitize if needed
        sanitize_fn_name = '_sanitize_export_test_{}'.format(handler_name)
        if hasattr(self, sanitize_fn_name):
            sanitize_func = getattr(self, sanitize_fn_name)
            expected_output = sanitize_func(expected_output)
            actual_output = sanitize_func(actual_output)

        assert expected_output == actual_output

