from schedules_tools.schedule_handlers import ScheduleHandlerBase
from schedules_tools import models
import sys
import datetime
import os
import logging

log = logging.getLogger(__name__)

try:
    from pyral import Rally, rallySettings
    additional_deps_satistifed = True
except ImportError:
    additional_deps_satistifed = False


class ScheduleHandler_rally(ScheduleHandlerBase):
    provide_export = False

    handle_deps_satisfied = additional_deps_satistifed

    @classmethod
    def is_valid_source(cls, handle=None):
        if not handle:
            handle = cls.handle
        if os.stat(handle).st_size < 1024:
            file_cont = open(handle).read()
            if 'WORKSPACE' in file_cont and 'PROJECT' in file_cont:
                return True
        return False

    def import_schedule(self):
        self.schedule = models.Schedule()
        start_time = None

        options = ['--config=%s' % self.handle]
        server, user, password, workspace, project = rallySettings(options)

        rally = Rally(server, user, password, workspace=workspace, project=project)

        rally_iter = self.options['rally_iter']
        self.schedule.name = rally_iter.strip()
        query_criteria = 'Iteration.Name = "%s"' % rally_iter

        response = rally.get('Iteration', fetch=True,
                             query='Name = "%s"' % rally_iter)
        if response.errors:
            sys.stdout.write("\n".join(response.errors))
            sys.exit(1)

        for iteration in response:
            print 'Iteration: %s (starts %s)' % (iteration.Name, iteration.StartDate)
            start_time = datetime.datetime.combine(
                datetime.datetime.strptime(iteration.StartDate[:10], '%Y-%m-%d'),
                datetime.time(8))
            break

        response = rally.get('UserStory', fetch=True, query=query_criteria, order="Rank")

        if response.errors:
            sys.stdout.write("\n".join(response.errors))
            sys.exit(1)

        index = 1
        if not start_time:
            start_time = datetime.datetime.combine(datetime.date.today(), datetime.time(8))
        max_end_time = start_time
        self.schedule.dStart = start_time

        for story in response:
            print story.Name
            t = models.Task(self.schedule, level=1)
            t.index = index
            index += 1
            t.name = story.Name.strip()
            t.dStart = start_time

            max_st_end_time = start_time
            story.Tasks.sort(key=lambda x: x.TaskIndex)
            for task in story.Tasks:
                print '-- %s  |  %sh  |  %s' % (task.Name, task.Estimate, task.Owner.Name)
                t_in = models.Task(self.schedule, level=2)
                t_in.index = index
                index += 1
                t_in.name = task.Name.strip()
                t_in.dStart = start_time
                t_in.dFinish = start_time + datetime.timedelta(hours=float(task.Estimate))
                max_st_end_time = max(max_end_time, t_in.dFinish)

                # look for resource
                resource_id = None
                for r_id, resource in self.schedule.resources.items():
                    if resource == task.Owner.Name:
                        resource_id = r_id
                        break
                if not resource_id:
                    resource_id = len(self.schedule.resources) + 1
                    self.schedule.resources[resource_id] = str(task.Owner.Name)

                t_in.resource = resource_id

                t.tasks.append(t_in)
            print ''
            t.dFinish = max_st_end_time
            max_end_time = max(max_end_time, t.dFinish)
            self.schedule.tasks.append(t)

        self.schedule.dFinish = max_end_time
        return self.schedule

