import datetime
import json
import logging
import os

from schedules_tools.schedule_handlers import ScheduleHandlerBase
from schedules_tools.models import Schedule, Task

log = logging.getLogger(__name__)


class ScheduleHandler_json(ScheduleHandlerBase):
    provide_export = True

    handle_deps_satisfied = True

    default_export_ext = 'json'

    changelog_date_format = '%Y-%m-%d'

    @classmethod
    def is_valid_source(cls, handle=None):
        if not handle:
            handle = cls.handle
        file_ext = os.path.splitext(handle)[1]

        if file_ext != '.json':
            return False
        try:
            with open(handle) as fd:
                json.load(fd)
        except ValueError:
            return False

        return True

    @staticmethod
    def _parse_timestamp(timestamp):
        number = int(timestamp)
        return datetime.datetime.fromtimestamp(number)

    def import_schedule(self):
        with open(self.handle) as fd:
            jsonobj = json.load(fd)

        schedule = Schedule()
        schedule.dStart = self._parse_timestamp(jsonobj['start'])
        schedule.dFinish = self._parse_timestamp(jsonobj['end'])
        schedule.slug = jsonobj['slug']
        schedule.name = jsonobj['name']

        if jsonobj.get('mtime', None):
            schedule.mtime = self._parse_timestamp(jsonobj['mtime'])
        schedule.ext_attr = jsonobj.get('ext_attr', {})
        schedule.resources = jsonobj.get('resources', {})
        schedule.flags_attr_id = jsonobj.get('flags_attr_id', None)
        # schedule.id_reg is built during parsing tasks

        if 'changelog' in jsonobj:
            changelogs = {}

            for rev, record in jsonobj['changelog'].items():
                record_date = datetime.datetime.strptime(
                    record['date'], self.changelog_date_format)
                item = {
                    'user': record['user'],
                    'date':  record_date,
                    'msg': record['msg']
                }
                changelogs[rev] = item
            schedule.changelog = changelogs

        # We don't parse phases here, because we are collecting them
        # during parsing tasks itself

        for subtaskobj in jsonobj['tasks']:
            task = self.import_task_from_json(schedule, subtaskobj, None)
            schedule.tasks.append(task)
        return schedule

    def import_task_from_json(self, schedule, jsonobj, parenttask):
        task = Task(schedule)

        task.index = jsonobj['index']
        task.level = jsonobj['_level']
        task.name = jsonobj['name']
        task.slug = jsonobj['slug']
        schedule.id_reg.add(task.slug)

        task.priority = jsonobj['priority']
        task.p_complete = jsonobj['complete']
        task.milestone = False
        if jsonobj['type'] == 'Milestone':
            task.milestone = True
        task.flags = jsonobj['flags']

        if 'link' in jsonobj:
            task.link = jsonobj['link']

        if 'note' in jsonobj:
            task.note = jsonobj['note']

        task.dStart = self._parse_timestamp(jsonobj['start'])
        task.dFinish = self._parse_timestamp(jsonobj['end'])

        schedule.used_flags |= set(task.flags)

        if 'tasks' in jsonobj:
            for subtaskobj in jsonobj['tasks']:
                subtask = self.import_task_from_json(schedule, subtaskobj, task)
                task.tasks.append(subtask)

        return task

    def export_schedule(self, out_file):
        json_schedule = self.export_schedule_as_dict()
        content = json.dumps(json_schedule,
                             sort_keys=True,
                             indent=4,
                             separators=(',', ': '))

        self._write_to_file(content, out_file)

        return content

    def export_schedule_as_dict(self):
        schedule_dict = dict()
        schedule_dict['slug'] = self.schedule.slug
        schedule_dict['name'] = self.schedule.name
        schedule_dict['start'] = self.schedule.dStart.strftime('%s')
        schedule_dict['end'] = self.schedule.dFinish.strftime('%s')

        if self.schedule.mtime:
            schedule_dict['mtime'] = self.schedule.mtime.strftime('%s')

        schedule_dict['resources'] = self.schedule.resources
        schedule_dict['used_flags'] = sorted(list(self.schedule.used_flags))
        schedule_dict['ext_attr'] = self.schedule.ext_attr
        schedule_dict['flags_attr_id'] = self.schedule.flags_attr_id

        # We intentionally don't export id_reg attribute here - it's collected
        # during import

        schedule_dict['changelog'] = self.schedule.changelog
        for log in self.schedule.changelog.itervalues():
            log['date'] = datetime.datetime.strftime(log['date'], '%Y-%m-%d')

        schedule_dict['tasks'] = []
        self.schedule.task_id_reg = set()

        for task in self.schedule.tasks:
            schedule_dict['tasks'].append(self.export_task_as_dict(task))

        return schedule_dict

    def export_task_as_dict(self, task, parent_slug=''):
        task_export = {}

        task_export['slug'] = task.slug
        task_export['index'] = task.index
        task_export['_level'] = task.level
        task_export['name'] = task.name
        task_export['priority'] = task.priority
        task_export['complete'] = task.p_complete
        task_export['type'] = task.get_type()
        task_export['flags'] = task.flags

        if task.note:
            task_export['note'] = task.note
        if task.link:
            task_export['link'] = task.link

        task_export['parentTask'] = parent_slug

        task_export['start'] = task.dStart.strftime('%s')
        task_export['end'] = task.dFinish.strftime('%s')

        if task.tasks:  # task has subtasks
            # prepare tasklist
            task_export['tasks'] = []

            for subtask in task.tasks:
                task_export['tasks'].append(self.export_task_as_dict(subtask, task.slug))

        return task_export
