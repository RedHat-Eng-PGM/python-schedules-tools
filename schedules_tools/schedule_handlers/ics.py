import datetime
import logging

from icalendar import Calendar, Event

from schedules_tools.schedule_handlers import ScheduleHandlerBase

logger = logging.getLogger(__name__)


class ScheduleHandler_ics(ScheduleHandlerBase):
    provide_export = True
    _datetime_format = '%Y%m%dT%H%M%SZ'
    _now = None

    def export_schedule(self, out_file, flat=False):
        self._now = datetime.datetime.now()
        
        cal = Calendar()
        cal_params = [
            ('prodid', '-//python-schedules-tools//ICS handler//'),
            ('version', '2.0'),
            ('summary', self.schedule.name),
            ('uid', self.schedule.slug)
        ]
        [cal.add(k, v) for k, v in cal_params]
        
        self.add_tasks_to_calendar(cal, self.schedule.tasks)
        content = cal.to_ical()
        
        with open(out_file, 'wb') as f:
            f.write(content)
        
        return content

    def add_tasks_to_calendar(self, calendar, tasks):
        for task in tasks:
            calendar.add_component(self.task2ical(task))
            self.add_tasks_to_calendar(calendar, task.tasks)


    def task2ical(self, task):
        event = Event()
        event['uid'] = '{}-{}'.format(task.index, task.slug)
        event['summary'] = task.name
        event['dtstart'] = task.dAcStart.strftime(self._datetime_format)
        event['dtend'] = task.dAcFinish.strftime(self._datetime_format)
        event['dtstamp'] = self._now.strftime(self._datetime_format)
        event['transp'] = 'TRANSPARENT'  # invisible to free/busy searches      
        event['description'] = task.note
        
        return event

