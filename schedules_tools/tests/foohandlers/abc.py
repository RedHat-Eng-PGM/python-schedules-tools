import logging

from schedules_tools.schedule_handlers import ScheduleHandlerBase


log = logging.getLogger(__name__)


class ScheduleHandler_abc(ScheduleHandlerBase):
    provide_export = True

    @staticmethod
    def is_valid_source(handle):
        return False

    # Schedule
    def export_schedule(self, output):
        with open(output, 'w+') as fd:
            fd.write(self.schedule.name)
