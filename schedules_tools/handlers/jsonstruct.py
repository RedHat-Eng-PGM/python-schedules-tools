from . import ScheduleHandlerBase
import datetime

# this block exists here only for compatibility purpose
try:
    import json
except ImportError:
    import simplejson as json


class ScheduleHandler_json(ScheduleHandlerBase):
    provide_export = True

    def import_schedule(self, handle):
        raise NotImplementedError

    def export_schedule(self, out_file, flat=False):
        json_schedule = dict()
        json_schedule['name'] = self.schedule.name
        json_schedule['version'] = self.schedule.version
        json_schedule['start'] = self.schedule.dStart.strftime('%s')
        json_schedule['end'] = self.schedule.dFinish.strftime('%s')

        now = datetime.datetime.now()
        json_schedule['now'] = now.strftime('%s')

        json_schedule['changelog'] = self.schedule.changelog
        for log in self.schedule.changelog.itervalues():
            log['date'] = datetime.datetime.strftime(log['date'], '%Y-%m-%d')

        json_schedule['tasks'] = []
        self.schedule.task_id_reg = set()

        if flat:
            add_func = json_schedule['tasks'].extend
        else:
            add_func = json_schedule['tasks'].append

        for task in self.schedule.tasks:
            add_func(self.task_export_json_obj(
                task, self.schedule.proj_id, self.schedule.proj_id, flat))

        # phases
        json_schedule['phases'] = []
        for phase in self.schedule.phases:
            json_schedule['phases'].append(self.task_export_json_phase(phase))

        fp = open(out_file, 'wb')
        json.dump(json_schedule, fp)

    def task_export_json_obj(self, task, id_prefix, proj_id, flat=False):
        task_export = {}
        tj_id = task.tjx_id
        if not tj_id:
            tj_id = self.schedule.get_unique_task_id(task, id_prefix)

        task_export['id'] = tj_id
        task_export['index'] = task.index
        task_export['_level'] = task.level
        task_export['name'] = task.name
        task_export['projectId'] = proj_id
        task_export['priority'] = task.priority
        task_export['complete'] = task.p_complete
        task_export['type'] = task.get_type()
        task_export['flags'] = task.flags

        if tj_id != id_prefix:  # not first task
            task_export['parentTask'] = id_prefix

        task_export['planStart'] = task.dStart.strftime('%s')
        task_export['planEnd'] = task.dFinish.strftime('%s')
        task_export['actualStart'] = task.dAcStart.strftime('%s')
        task_export['actualEnd'] = task.dAcFinish.strftime('%s')

        task_list = [task_export]

        if task.tasks:  # task has subtasks
            # prepare tasklist
            if flat:
                add_func = task_list.extend
            else:
                task_export['tasks'] = []
                add_func = task_export['tasks'].append

            for subtask in task.tasks:
                add_func(self.task_export_json_obj(
                    subtask, tj_id, proj_id, flat))

        if flat:
            return task_list
        else:
            return task_export

    def task_export_json_phase(self, phase):
        phase_export = dict()
        phase_export['name'] = phase.name
        phase_export['complete'] = phase.p_complete
        phase_export['planStart'] = phase.dStart.strftime('%s')
        phase_export['planEnd'] = phase.dFinish.strftime('%s')
        phase_export['actualStart'] = phase.dAcStart.strftime('%s')
        phase_export['actualEnd'] = phase.dAcFinish.strftime('%s')

        return phase_export
