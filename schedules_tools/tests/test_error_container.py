import testtools
from schedules_tools import ErrorContainer


class TestErrorContainer(testtools.TestCase):
    container = None

    def setUp(self):
        super(TestErrorContainer, self).setUp()
        self.container = ErrorContainer()

    def test_add_item(self):
        assert len(self.container.import_errors) == 0
        self.container.add_error_log('cat1', 'msg1')
        self.container.add_error_log('cat1', 'msg1')
        self.container.add_error_log('cat1', 'msg1')
        self.container.add_error_log('cat1', 'msg1')
        assert len(self.container.import_errors) == 4

    def test_flush_errors(self):
        self.container.add_error_log('cat1', 'msg1')
        assert len(self.container.import_errors) == 1
        self.container.flush_errors()
        assert len(self.container.import_errors) == 0

    def test_get_logs_empty(self):
        assert self.container.get_error_logs() is None
        assert self.container.get_error_logs(pretty=True) is None

    def test_get_logs_non_empty(self):
        self.container.add_error_log('cat1', 'msg1')

        # get_errors_logs returns iterable, so str() is needed
        assert 'msg1' in str(self.container.get_error_logs())
        assert 'msg1' in self.container.get_error_logs(pretty=True)

