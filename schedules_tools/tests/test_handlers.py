import json
import logging
import os
import pytest
import re
import shutil

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
        argnames = ['handler_name', 'export_schedule_file']
        argvalues = metafunc.cls.scenarios_export_combinations
        metafunc.parametrize(argnames, argvalues)


class TestHandlers(object):
    intermediary_reference_file = 'intermediary-struct-reference.json'
    schedule_files_dir = 'schedule_files'
    basedir = os.path.dirname(os.path.realpath(__file__))

    scenarios_import_combinations = [
        ('msp', 'import-schedule-msp.xml'),
        ('json', 'import-schedule-json.json'),
        ('tjx2', 'import-schedule-tjx2.tjx'),
    ]
    scenarios_export_combinations = [
        ('msp', 'export-schedule-msp.xml'),
        ('json', 'export-schedule-json.json'),
        ('ics', 'export-schedule-ics.ics'),
    ]

    def _sanitize_export_test_ics(self, content):
        return re.sub('DTSTAMP:[0-9]+T[0-9]+Z', 'DTSTAMP:20170101T010101Z', content)

    @staticmethod
    def _clean_interm_struct(input_dict):
        """Removes keys that is not needed for comparison"""
        keys_to_remove = ['unique_id_re', 'id_reg', 'ext_attr', 'flags_attr_id',
                          'resources']
        for key in keys_to_remove:
            if key in input_dict:
                input_dict.pop(key)

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

    def test_import(self, handler_name, import_schedule_file):
        converter_options = {
            'source_storage_format': 'local'
        }
        full_import_schedule_file = os.path.join(self.basedir, self.schedule_files_dir,
                                                 import_schedule_file)

        conv = ScheduleConverter()
        schedule = conv.import_schedule(full_import_schedule_file,
                                        schedule_src_format=handler_name,
                                        options=converter_options)
        assert 0 == len(schedule.errors_import)

        imported_schedule_dict = schedule.dump_as_dict()
        self._clean_interm_struct(imported_schedule_dict)

        interm_reference_file = os.path.join(self.basedir,
                                             self.intermediary_reference_file)
        regenerate = os.environ.get('REGENERATE', False) == 'true'
        if regenerate:
            logger.info('test_import: Regenerating interm. reference file from imported schedule.')

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

    def test_export(self, handler_name, export_schedule_file, tmpdir):
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
        conv.export_schedule(export_output_filename, handler_name)
        actual_output = export_output_file.read()

        regenerate = os.environ.get('REGENERATE', False) == 'true'

        if regenerate:
            logger.info('test_export: Regenerating exported file from reference schedule.')
            shutil.copy(export_output_filename, full_export_schedule_file)

        with open(full_export_schedule_file) as fd:
            expected_output = fd.read()
        
        # sanitize if needed
        if hasattr(self, '_sanitize_export_test_{}'.format(handler_name)):
            sanitize_func = getattr(self, '_sanitize_export_test_{}'.format(handler_name))
            expected_output = sanitize_func(expected_output)
            actual_output = sanitize_func(actual_output)

        assert expected_output == actual_output

