from schedules_tools import testrunner
from schedules_tools import discovery
import logging

logger = logging.getLogger(__name__)
discovery.schedule_handlers.run_discovery()

def pytest_generate_tests(metafunc):
    idlist = []
    argvalues = []
    for scenario in metafunc.cls.combinations:
        idlist.append(scenario[0])
        items = scenario[1].items()
        argnames = [x[0] for x in items]
        argvalues.append(([x[1] for x in items]))
    metafunc.parametrize(argnames, argvalues, ids=idlist, scope="class")

IMPORT = 'import'
EXPORT = 'export'


class TestHandlers(object):
    combinations = [
        ('tjx-in', {'handler': 'tjx',
                    'reference': 'schedules_tools/tests/ref.json',
                    'testfile': 'schedules_tools/tests/data/input.tjx',
                    'action': IMPORT}),
        ('tjx-out', {'handler': 'tjx',
                     'reference': 'schedules_tools/tests/ref.json',
                     'testfile': 'schedules_tools/tests/data/output.tjx',
                     'action': EXPORT}),
        ('msp-in', {'handler': 'msp',
                    'reference': 'schedules_tools/tests/ref.json',
                    'testfile': 'schedules_tools/tests/data/input.xml',
                    'action': IMPORT}),
        ('msp-out', {'handler': 'msp',
                     'reference': 'schedules_tools/tests/ref.json',
                     'testfile': 'schedules_tools/tests/data/output.xml',
                     'action': EXPORT}),
        ('tjx2-in', {'handler': 'tjx2',
                     'reference': 'schedules_tools/tests/ref.json',
                     'testfile': 'schedules_tools/tests/data/input-v2.tjx',
                     'action': IMPORT}),
        ('html-out', {'handler': 'html',
                      'reference': 'schedules_tools/tests/ref.json',
                      'testfile': 'schedules_tools/tests/data/output.html',
                      'action': EXPORT}),
        ('json-out', {'handler': 'json',
                      'reference': 'schedules_tools/tests/ref.json',
                      'testfile': 'schedules_tools/tests/data/output-struct.json',
                      'action': EXPORT}),
        ('jsonflat-out', {'handler': 'jsonflat',
                          'reference': 'schedules_tools/tests/ref.json',
                          'testfile': 'schedules_tools/tests/data/output-flat.json',
                          'action': EXPORT}),
    ]

    def test_handler(self, handler, reference, testfile, action):
        runner = testrunner.TestRunner(handler, reference)
        if action == EXPORT:
            runner.test_output(testfile)
        elif action == IMPORT:
            runner.test_input(testfile)
        else:
            logger.warn('Unknown action to test: {}'.format(action))
