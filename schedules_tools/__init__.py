from datetime import datetime
from pprint import pformat

# predefined categories of rough location of error
ERR_CVS = 'cvs'
ERR_SCHEDULE = 'schedule'
ERR_BUILDING = 'building'


class ErrorContainer(object):
    import_errors = []

    def __init__(self):
        self.import_errors = []

    def add_error_log(self, category, message):
        item = {
            'timestamp': datetime.now(),
            'category': category,
            'message': message
        }
        self.import_errors.append(item)

    def get_error_logs(self, pretty=False):
        if not self.import_errors:
            return None
        if pretty:
            return pformat(self.import_errors)

        return self.import_errors

    def flush_errors(self):
        self.import_errors = list()


error_container = ErrorContainer()
