from schedules_tools.handlers import ScheduleHandlerBase
import logging

logger = logging.getLogger(__name__)


class ScheduleHandler_tjx(ScheduleHandlerBase):
    provide_export = True

    @staticmethod
    def is_valid_source(handle):
        return False

    # Schedule
    def export_schedule(self, output):
        with open(output, 'w+') as fd:
            fd.write('schedule.name={}'.format(self.schedule.name))
