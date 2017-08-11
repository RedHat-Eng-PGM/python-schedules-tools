from datetime import datetime

# General exception type for subclassing
class SchedulesToolsException(Exception):
    source = None
    datetime = None

    def __init__(self, *args, **kwargs):
        self.source = kwargs.get('source', None)
        self.datetime = datetime.now()
        super(SchedulesToolsException, self).__init__(*args)


class CmdException(SchedulesToolsException):
    pass
