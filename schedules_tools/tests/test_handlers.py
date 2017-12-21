import datetime
import json
import logging
import os
import pytest
import re
import shutil
# TODO(mpavlase): don't fail if the module is not installed
from smartsheet import Smartsheet

from schedules_tools.converter import ScheduleConverter
from schedules_tools.tests import jsondate
from schedules_tools.models import Schedule

logger = logging.getLogger(__name__)


def pytest_generate_tests(metafunc):
    source_function = metafunc.function.__name__

    if source_function == 'test_import':
        argnames = ['handler_name', 'import_schedule_file']
        argvalues = metafunc.cls.scenarios_import_combinations
        metafunc.parametrize(argnames, argvalues)
    elif source_function == 'test_export':
        argnames = ['handler_name', 'export_schedule_file', 'flat', 
                    'flag_show', 'flag_hide', 
                    'options']
        argvalues = metafunc.cls.scenarios_export_combinations
        metafunc.parametrize(argnames, argvalues)


class TestHandlers(object):
    intermediary_reference_file = 'intermediary-struct-reference.json'
    schedule_files_dir = 'schedule_files'
    basedir = os.path.dirname(os.path.realpath(__file__))

    scenarios_import_combinations = [
        ('msp', 'import-schedule-msp.xml'),
        ('smartsheet', ''),
        ('json', 'import-schedule-json.json'),
        ('tjx2', 'import-schedule-tjx2.tjx'),
    ]
    scenarios_export_combinations = [
        ('msp', 'export-schedule-msp.xml', False, [], [], {}),
        ('json', 'export-schedule-json.json', False, [], [], {}),
        ('json', 'export-schedule-json.json-flags', False, ['flag1'], ['flag2'], {}),
        ('json', 'export-schedule-json-flat.json', True, [], [], {}),
        ('json', 'export-schedule-json-flat-flags.json', True, ['flag1'], ['flag2'], {}),
        ('ics', 'export-schedule-ics.ics', False, [], [], {}),
        ('html', 'export-schedule-html.html', False, [], [], {}),
        ('html', 'export-schedule-html-options.html', False, [], [], dict(html_title='Test title',
                                                                          html_table_header='<p>Test header</p>')),
    ]

    smartsheet_columns_ids = ()
    smartsheet_sheet_id = None
    smartsheet_client = None

    def _sanitize_export_test_ics(self, content):
        return re.sub('DTSTAMP:[0-9]+T[0-9]+Z', 'DTSTAMP:20170101T010101Z', content)

    def _clean_interm_struct(self, input_dict):
        """Removes keys that is not needed for comparison,
        unify time-part of dates"""
        keys_to_remove = ['unique_id_re', 'id_reg', 'ext_attr', 'flags_attr_id',
                          'resources']
        for key in keys_to_remove:
            if key in input_dict:
                input_dict.pop(key)

        for task in input_dict['tasks']:
            self._clear_task_time(task)

    def _clear_task_time(self, task):
        """For comparison purpose we ignore hours and minutes of task."""
        task['dStart'] = task['dStart'].replace(hour=0, minute=0)
        task['dAcStart'] = task['dAcStart'].replace(hour=0, minute=0)
        task['dFinish'] = task['dFinish'].replace(hour=0, minute=0)
        task['dAcFinish'] = task['dAcFinish'].replace(hour=0, minute=0)

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

    def fixture_import_smartsheet(self):
        token = os.environ.get('SMARTSHEET_TOKEN', None)
        if not token:
            pytest.fail('You need to specify environment variable '
                        'SMARTSHEET_TOKEN to run smartsheet tests.')
        self.smartsheet_client = Smartsheet(token)

        # Create a new sheet based on public Project template ('from_id' arg)
        sheet_spec = self.smartsheet_client.models.Sheet({
            'name': 'Test project 10',
            'from_id': 5066554783098756,
        })
        resp = self.smartsheet_client.Home.create_sheet_from_template(sheet_spec)
        assert resp.message == 'SUCCESS'

        self.smartsheet_sheet_id = resp.result.id

        column_spec_flags = self.smartsheet_client.models.Column({
            'title': 'Flags',
            'type': 'TEXT_NUMBER',
            'index': 4,
        })
        column_spec_link = self.smartsheet_client.models.Column({
            'title': 'Link',
            'type': 'TEXT_NUMBER',
            'index': 4,
        })
        resp = self.smartsheet_client.Sheets.add_columns(
            self.smartsheet_sheet_id,
            [column_spec_flags, column_spec_link]
        )
        assert resp.message == 'SUCCESS'

        sheet = self.smartsheet_client.Sheets.get_sheet(self.smartsheet_sheet_id)

        # get columns ID
        self.smartsheet_columns_ids = (
            sheet.columns[0].id,  # task name
            sheet.columns[1].id,  # duration
            sheet.columns[2].id,  # start
            sheet.columns[3].id,  # finish
            sheet.columns[4].id,  # flags
            sheet.columns[5].id,  # link
            sheet.columns[8].id,  # complete
            sheet.columns[10].id,  # comment
        )

        def format_date(year, month, day):
            return datetime.datetime(year, month, day).isoformat()

        task_proj10 = self._smartsheet_create_row(
            name='Test project 10')
        task_test1 = self._smartsheet_create_row(
            name='Test 1', parent_id=task_proj10)
        task_development = self._smartsheet_create_row(
            name='Development',
            duration='21d',
            start=format_date(2000, 1, 1),
            link='Link: https://github.com/1',
            complete=0.36,
            parent_id=task_test1)
        task_dev = self._smartsheet_create_row(
            name='Dev',
            duration='~0',
            start=format_date(2000, 1, 21),
            complete=0.4,
            parent_id=task_test1)
        task_testing = self._smartsheet_create_row(
            name='Testing Phase',
            duration='14d',
            start=format_date(2000, 1, 21),
            flags='Flags: flag1',
            complete=0.9,
            parent_id=task_test1)
        task_release = self._smartsheet_create_row(
            name='Release',
            duration='~0',
            start=format_date(2000, 1, 21),
            link='Link: https://github.com/2',
            flags='Flags: flag2',
            parent_id=task_test1)
        task_test2 = self._smartsheet_create_row(
            name='Test 2',
            parent_id=task_proj10)
        task_first = self._smartsheet_create_row(
            name='First task',
            duration='3d',
            start=format_date(2000, 2, 3),
            parent_id=task_test2)
        task_another = self._smartsheet_create_row(
            name='Another task',
            duration='~0',
            start=format_date(2000, 2, 5),
            flags='Flags: flag1,flag2,flag3',
            comment='test2 note',
            parent_id=task_test2)

        converter_options = {
            'smartsheet_token': token,
        }

        # returns tuple: (handle, converter_options)
        yield self.smartsheet_sheet_id, converter_options

        # teardown 'phase'
        self.client.Sheets.delete_sheet(self.smartsheet_sheet_id)

    def _smartsheet_create_row(self, name, duration=None, start=None,
                               finish=None, flags=None, link=None,
                               complete=None, comment=None, parent_id=None):
        """
        Helper function to create new row at the end of sheet/parent subtree.

        Args:
            name: task name
            duration: length of the task as string (i.e.: '3d', '~0')
            start: date as ISO-8601 format
            finish: date as ISO-8601 format
            flags: string (i.e.: 'qe, dev', 'flags: qe, dev')
            link: URL string
            comment: string
            complete: percent complete as float within range 0.0 - 1.0
            parent_id: parent row ID, or optionally None (insert it as root node)

        Returns:
            ID of just inserted row
        """
        row = self.smartsheet_client.models.Row()
        row.parent_id = parent_id
        row.to_bottom = True

        columns = (name, duration, start, finish, flags, link, complete, comment)
        for column_id, value in zip(self.smartsheet_columns_ids, columns):
            if value is None:
                continue

            row.cells.append({
                'column_id': column_id,
                'value': value
            })
        resp = self.smartsheet_client.Sheets.add_rows(self.smartsheet_sheet_id, [row])
        assert resp.message == 'SUCCESS', resp.result.message
        assert 1 == len(resp.result)

        return resp.result[0].id

    @pytest.fixture(scope='function')
    def fixture_import_handle(self, request):
        """
        Generic pytest fixture that provides arguments for import_schedule meth.
        If there is specified 'import_schedule_file' value of argument,
        its considered as filename of file-based handle.
        Otherwise will try to call 'fixture_import_handlename' method that
        provides these arguments (handle, options).
        Also it works as setup/teardown-like method of the handle's test
        (using yield within the 'fixture_import_' method).
        """
        import_schedule_file = request.getfuncargvalue('import_schedule_file')
        handler_name = request.getfuncargvalue('handler_name')
        handle = None
        converter_options = dict()

        if import_schedule_file:
            handle = os.path.join(self.basedir, self.schedule_files_dir,
                                  import_schedule_file)
            converter_options = {
                'source_storage_format': 'local'
            }
            yield handle, converter_options
        else:
            callback_name = 'fixture_import_' + handler_name

            try:
                fixture_fn = self.__getattribute__(callback_name)
                fixture_value = fixture_fn()  # expect to return tuple (handle, options)
                yield fixture_value.next()

                # this line will cause final exit of this function
                fixture_value.next()
            except AttributeError:
                yield handle, converter_options

    def test_import(self, fixture_import_handle, handler_name, import_schedule_file):
        handle, converter_options = fixture_import_handle

        conv = ScheduleConverter()
        schedule = conv.import_schedule(handle,
                                        schedule_src_format=handler_name,
                                        options=converter_options)
        assert 0 == len(schedule.errors_import)

        imported_schedule_dict = schedule.dump_as_dict()
        self._clean_interm_struct(imported_schedule_dict)

        interm_reference_file = os.path.join(self.basedir,
                                             self.intermediary_reference_file)
        regenerate = os.environ.get('REGENERATE', False) == 'true'
        if regenerate:
            logger.info('test_import: Regenerating interm. reference file'
                        'from imported schedule.')

            with open(interm_reference_file, 'w+') as fd:
                jsondate.dump(imported_schedule_dict,
                              fd,
                              sort_keys=True,
                              indent=4,
                              separators=(',', ': '))

        with open(interm_reference_file) as fd:
            reference_dict = json.load(fd, object_hook=self._convert_struct_unicode_to_str)
        self._clean_interm_struct(reference_dict)

        assert reference_dict == imported_schedule_dict

    def test_export(self, handler_name, export_schedule_file, 
                    flat, flag_show, flag_hide, options,
                    tmpdir):
        interm_reference_file = os.path.join(self.basedir,
                                             self.intermediary_reference_file)

        full_export_schedule_file = os.path.join(self.basedir, self.schedule_files_dir,
                                                 export_schedule_file)
        with open(interm_reference_file) as fd:
            intermediary_input_dict = jsondate.load(fd, object_hook=self._convert_struct_unicode_to_str)

        intermediary_input = Schedule.load_from_dict(intermediary_input_dict)
        export_output_file = tmpdir.join('exported_file')
        export_output_filename = str(export_output_file)

        conv = ScheduleConverter(intermediary_input)
        
        if flat:
            conv.schedule.make_flat()
        
        conv.schedule.filter_flags(flag_show, flag_hide)
        
        conv.export_schedule(export_output_filename, handler_name, options=options)
        actual_output = export_output_file.read()

        regenerate = os.environ.get('REGENERATE', False) == 'true'

        if regenerate:
            logger.info('test_export: Regenerating exported file from reference schedule.')
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

