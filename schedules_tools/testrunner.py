import tempfile
import os

from schedules_tools import jsondate
from schedules_tools import converter
from schedules_tools import models


class TestRunner(object):
    """
    This class handles testing schedule import and export of schedules.

    If some test comparison fails (expected content is different of actual),
    there is a feature that stores input/output content into directory to help
    debugging (test_failures_output_dir).
    """
    handler_name = None
    options = None
    json_reference_file = None
    test_failures_output_dir = None
    test_id = None

    def __init__(self,
                 handler_name,
                 json_reference_file,
                 options=None,
                 test_id=None,
                 test_failures_output_dir=None,
                 wipeout_failures_output_dir=False):
        """
        Args:
            handler_name: 'tjx'|'tjx2'|'msp'|'jsonstruct'|...
            json_reference_file: filename of JSON dump that contains correct
                (=reference) test data to compare with actual
            options: dict of another options those are passed to schedule_import
            test_id: string label of actual test, it's used for naming
                debug files, if some test fails
            test_failures_output_dir: path to directory where would be stored
                test data of failed tests
        """
        self.handler_name = handler_name
        self.options = options
        self.json_reference_file = json_reference_file
        self.test_id = test_id
        self.test_failures_output_dir = test_failures_output_dir

    def make_json_reference(self, input_file):
        """
        Takes input file and produce JSON dump and store it into
        json_reference_file (constructor of class).

        Args:
            input_file: source of data to produce reference json representation
                        for further comparison in import/export tests.
        """
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

    def _dump_output_as_file(self, expected_content, test_content):
        """
        Store test data into files to help debugging tests (differences
        between conversions).
        Path to these files is stored in 'test_failures_output_dir' variable.

        Args:
            expected_content: expected content
            test_content: actual result of schedule conversion
        """
        if not (self.test_failures_output_dir and
                self.test_id):
            return

        output_file_prefix = os.path.join(self.test_failures_output_dir,
                                          self.test_id)
        with open(output_file_prefix + '_expected_content.json', 'w+') as fd:
            fd.write(expected_content)

        with open(output_file_prefix + '_actual_content.json', 'w+') as fd:
            fd.write(test_content)

    @staticmethod
    def _dict_to_string(input_dict):
        return jsondate.dumps(input_dict,
                              sort_keys=True,
                              indent=4,
                              separators=(',', ': '))

    def test_import(self, input_file):
        """
        Takes handle (input_file) to import source data of schedule (result is
        Schedule object), produces JSON dump and compare that with reference dump
        (json_reference_file).
        """
        reference_str = self._load_reference_as_json_str()
        conv = converter.ScheduleConverter()
        conv.import_schedule(input_file,
                             schedule_src_format=self.handler_name,
                             options=self.options)
        assert len(conv.schedule.errors_import) == 0
        input_dict = conv.schedule.dump_as_dict()
        input_dict['mtime'] = None
        input_str = self._dict_to_string(input_dict)

        if input_str != reference_str:
            self._dump_output_as_file(reference_str, input_str)

        assert input_str == reference_str, (
            'Imported schedule differs, check dumped content at %s' % self.test_failures_output_dir)

    def test_export(self, reference_file, patch_output_callback=None):
        """
        Takes reference JSON dump (json_reference_file) to fill Schedule object
        and pass it into Converter to produce exported output (a file).
        This exported file is finally compared with already stored output (reference_file)

        Args:
            reference_file: expected result of export
            patch_output_callback: function (callable object) to alter test content before comparing.
        """
        source_dict = self._load_reference_as_dict()
        source_schedule = models.Schedule.load_from_dict(source_dict)
        _, temp_export_file = tempfile.mkstemp()
        conv = converter.ScheduleConverter(source_schedule)
        conv.export_schedule(temp_export_file,
                             target_format=self.handler_name)

        with open(temp_export_file) as fd:
            exported_content = fd.read()
        os.unlink(temp_export_file)

        with open(reference_file) as fd:
            reference_output = fd.read()

        # Patch outputs, if needed
        if patch_output_callback and callable(patch_output_callback):
            exported_content = patch_output_callback(exported_content)
            reference_output = patch_output_callback(reference_output)

        if reference_output != exported_content:
            self._dump_output_as_file(reference_output, exported_content)

        assert exported_content == reference_output, (
            'Output differs, checkdumped content at %s' % self.test_failures_output_dir)
