from schedules_tools import testrunner
from schedules_tools import discovery
import logging
import os

logger = logging.getLogger(__name__)
discovery.schedule_handlers.run_discovery()
discovery.storage_handlers.run_discovery()

BASE_DIR = os.path.dirname(os.path.realpath(__file__))


def pytest_generate_tests(metafunc):
    idlist = []
    argvalues = []
    for scenario in metafunc.cls.test_suite:
        for combination in scenario['combinations']:
            idlist.append(combination[0])
            items = combination[1].items()
            argnames = ['basedir'] + [x[0] for x in items]
            argvalues.append([scenario['basedir']] + [x[1] for x in items])
    metafunc.parametrize(argnames, argvalues, ids=idlist, scope="class")

IMPORT = 'import'
EXPORT = 'export'


class TestHandlers(object):
    test_suite = [
        {'basedir': BASE_DIR,
         'combinations': [
            ('tjx-in', {'handler': 'tjx',
                        'reference': 'ref.json',
                        'testfile': 'data/input.tjx',
                        'action': IMPORT,
                        'teardown': '',
                        }),
            ('tjx-out', {'handler': 'tjx',
                         'reference': 'ref.json',
                         'testfile': 'data/output.tjx',
                         'action': EXPORT,
                         'teardown': ''}),
            ('msp-in', {'handler': 'msp',
                        'reference': 'ref.json',
                        'testfile': 'data/input.xml',
                        'action': IMPORT,
                        'teardown': ''}),
            ('msp-out', {'handler': 'msp',
                         'reference': 'ref.json',
                         'testfile': 'data/output.xml',
                         'action': EXPORT,
                         'teardown': ''}),
            ('tjx2-in', {'handler': 'tjx2',
                         'reference': 'ref.json',
                         'testfile': 'data/input-v2.tjx',
                         'action': IMPORT,
                         'teardown': ''}),
            ('html-out', {'handler': 'html',
                          'reference': 'ref.json',
                          'testfile': 'data/output.html',
                          'action': EXPORT,
                          'teardown': ''}),
            ('json-out', {'handler': 'json',
                          'reference': 'ref.json',
                          'testfile': 'data/output-struct.json',
                          'action': EXPORT,
                          'teardown': ''}),
            ('jsonflat-out', {'handler': 'jsonflat',
                              'reference': 'ref.json',
                              'testfile': 'data/output-flat.json',
                              'action': EXPORT,
                              'teardown': ''}),
            ]
         }
    ]

    def test_handler(self, handler, basedir, reference, testfile, action, teardown):
        testfile_abspath = os.path.join(basedir, testfile)
        reffile_abspath = os.path.join(basedir, reference)
        options = {
            'source_storage_format': 'local'
        }
        runner = testrunner.TestRunner(handler, reffile_abspath, options=options)
        if action == EXPORT:
            runner.test_output(testfile_abspath)
        elif action == IMPORT:
            runner.test_input(testfile_abspath)
        else:
            logger.warn('Unknown action to test: {}'.format(action))

        if teardown:
            teardown_method = self.__getattribute__(teardown)
            teardown_method(handler, basedir, reference, testfile, action)
