import tempfile
import os
from schedules_tools import jsondate
from schedules_tools import converter
from schedules_tools import models


class TestRunner(object):
    handler_name = None
    options = None
    json_reference_file = None

    def __init__(self, handler_name, json_reference_file, options=None):
        """
        Args:
            handler_name: name as str, such as 'tjx'
            json_reference_file: reference to make comparison
        """
        self.handler_name = handler_name
        self.options = options
        self.json_reference_file = json_reference_file

    def make_json_reference(self, input_file):
        conv = converter.ScheduleConverter()
        conv.import_schedule(input_file,
                             schedule_src_format=self.handler_name)
        input_dict = conv.schedule.dump_as_dict()
        with open(self.json_reference_file, 'w+') as fd:
            # pretty print output to be able do diff outside this tool
            jsondate.dump(
                input_dict, fd,
                sort_keys=True,
                indent=4,
                separators=(',', ': ')
            )

    def _load_reference_as_dict(self):
        with open(self.json_reference_file) as fd:
            return jsondate.load(fd)

    def _load_reference_as_json_str(self):
        json_loaded = self._load_reference_as_dict()
        json_loaded['mtime'] = None
        # load and dump again to not be sensitive by whitespaces etc.
        return self._dict_to_string(json_loaded)

    @staticmethod
    def _dict_to_string(input_dict):
        return jsondate.dumps(input_dict, sort_keys=True)

    def test_input(self, input_file):
        reference_str = self._load_reference_as_json_str()
        conv = converter.ScheduleConverter()
        conv.import_schedule(input_file,
                             schedule_src_format=self.handler_name,
                             options=self.options)
        input_dict = conv.schedule.dump_as_dict()
        input_dict['mtime'] = None
        input_str = self._dict_to_string(input_dict)

        assert input_str == reference_str

    def test_output(self, output_file, patch_output=None):
        reference_dict = self._load_reference_as_dict()
        reference_schedule = models.Schedule.load_from_dict(reference_dict)
        _, temp_reference_file = tempfile.mkstemp()
        conv = converter.ScheduleConverter(reference_schedule)
        conv.export_schedule(temp_reference_file,
                             target_format=self.handler_name)

        with open(temp_reference_file) as fd:
            reference = fd.read()
        os.unlink(temp_reference_file)

        with open(output_file) as fd:
            test_out = fd.read()

        # Patch outputs, if needed
        if patch_output and callable(patch_output):
            reference = patch_output(reference)
            test_out = patch_output(test_out)

        assert reference == test_out
