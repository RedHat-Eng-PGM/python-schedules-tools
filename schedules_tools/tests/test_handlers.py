from schedules_tools import testrunner
import logging
import os
import re

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.realpath(__file__))


def pytest_generate_tests(metafunc):
    idlist = []
    argvalues = []
    for scenario in metafunc.cls.test_suite:
        for combination in scenario['combinations']:
            test_id = combination[0]
            idlist.append(test_id)
            items = combination[1].items()
            argnames = ['basedir', 'test_id'] + [x[0] for x in items]
            argvalues.append([scenario['basedir'], test_id] + [x[1] for x in items])
    metafunc.parametrize(argnames, argvalues, ids=idlist, scope="class")


IMPORT = 'import'
EXPORT = 'export'


class TestHandlers(object):
    test_failures_output_dir = 'failed_tests_output'
    test_suite = [
        {'basedir': BASE_DIR,
         'combinations': [
#             ('tjx-in', {'handler': 'tjx',
#                         'reference': 'ref.json',
#                         'testfile': 'data/input.tjx',
#                         'action': IMPORT,
#                         'patch_output': '',
#                         'teardown': '',
#                         }),
#             ('tjx2-in', {'handler': 'tjx2',
#                          'reference': 'ref-tjx2.json',
#                          'testfile': 'data/input-v2.tjx',
#                          'action': IMPORT,
#                          'patch_output': '',
#                          'teardown': ''}),
#             ('msp-in', {'handler': 'msp',
#                         'reference': 'ref-msp.json',
#                         'testfile': 'data/input.xml',
#                         'action': IMPORT,
#                         'patch_output': '',
#                         'teardown': ''}),
#             ('msp-out', {'handler': 'msp',
#                          'reference': 'ref.json',
#                          'testfile': 'data/output.xml',
#                          'action': EXPORT,
#                          'patch_output': '',
#                          'teardown': ''}),
#             ('html-out', {'handler': 'html',
#                           'reference': 'ref.json',
#                           'testfile': 'data/output.html',
#                           'action': EXPORT,
#                           'patch_output': '',
#                           'teardown': ''}),
            ('json-out', {'handler': 'json',
                          'reference': 'ref.json',
                          'testfile': 'data/output-struct.json',
                          'action': EXPORT,
                          'patch_output': '_mask_json_now_field',
                          'teardown': ''}),
            ('jsonflat-out', {'handler': 'jsonflat',
                              'reference': 'ref.json',
                              'testfile': 'data/output-flat.json',
                              'action': EXPORT,
                              'patch_output': '_mask_json_now_field',
                              'teardown': ''}),
            ]
         }
    ]

    def test_handler(self, handler, basedir, test_id, reference, testfile,
                     action, patch_output, teardown):
        """

        Args:
            handler: name of handler to test ('tjx'|'msp'|'html'|'json'|'jsonflat'...)
            basedir: path used to locate reference and test files in
            test_id: label/caption of actual parametrized combination test case
            reference: JSON file to compare with test outputs
            testfile: File path that will be converted
            action: ('import'|'export')
            patch_output: Used in export only. Function name (string) in the same
                          class to patch reference and test output
            teardown: Function name (string) that will run always after asserting,
                      usually to cleanup side products of test

        Returns:

        """
        testfile_abspath = os.path.join(basedir, testfile)
        reffile_abspath = os.path.join(basedir, reference)
        test_failures_output_dir = os.path.join(basedir,
                                                self.test_failures_output_dir)
        if not os.path.exists(test_failures_output_dir):
            os.mkdir(test_failures_output_dir)

        options = {
            'source_storage_format': 'local'
        }
        patch_method = None
        runner = testrunner.TestRunner(
            handler,
            reffile_abspath,
            options=options,
            test_id=test_id,
            test_failures_output_dir=test_failures_output_dir)

        try:
            if action == EXPORT:
                if patch_output:
                    patch_method = self.__getattribute__(patch_output)

                runner.test_output(testfile_abspath, patch_method)
            elif action == IMPORT:
                runner.test_input(testfile_abspath)
            else:
                logger.warn('Unknown action to test: {}'.format(action))
        finally:
            if teardown:
                teardown_method = self.__getattribute__(teardown)
                teardown_method(handler, basedir, reference, testfile, action)

    def _mask_json_now_field(self, input_str):
        """JSON format contains field "now" with current timestamp, so output
        is always uniq. To be able to compare two outputs, we need to ignore
        this field, by replacing to static string.
        """
        return re.sub('"now": "\d+"', '"now": "123456789"', input_str)
