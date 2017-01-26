from schedules_tools.handlers import msp
from schedules_tools.handlers import strptime
from pyral import Rally, rallySettings
from schedules_tools import models
import sys
import datetime
import os


class ScheduleHandler_rally(msp.ScheduleHandler_msp):
    provide_export = False

    @staticmethod
    def is_valid_source(file_path):
        if os.stat(file_path).st_size < 1024:
            file_cont = open(file_path).read()
            if 'WORKSPACE' in file_cont and 'PROJECT' in file_cont:
                return True
        return False

    # Schedule
    def import_schedule(self, rally_cfg_file):
        start_time = None

        options = ['--config=%s' % rally_cfg_file]
        server, user, password, workspace, project = rallySettings(options)

        rally = Rally(server, user, password, workspace=workspace, project=project)

        query_criteria = 'Iteration.Name = "%s"' % self.rally_iter

        response = rally.get('Iteration', fetch=True,
                             query='Name = "%s"' % self.rally_iter)
        if response.errors:
            sys.stdout.write("\n".join(response.errors))
            sys.exit(1)

        for iteration in response:
            print 'Iteration: %s (starts %s)' % (iteration.Name, iteration.StartDate)
            start_time = datetime.datetime.combine(
                strptime(iteration.StartDate[:10], '%Y-%m-%d'),
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
        self.dStart = start_time

        for story in response:
            print story.Name
            t = models.Task(schedule=self, level=1)
            t.index = index
            index += 1
            t.name = story.Name
            t.dStart = start_time

            max_st_end_time = start_time
            story.Tasks.sort(key=lambda x: x.TaskIndex)
            for task in story.Tasks:
                print '-- %s  |  %sh  |  %s' % (task.Name, task.Estimate, task.Owner.Name)
                t_in = models.Task(schedule=self, level=2)
                t_in.index = index
                index += 1
                t_in.name = task.Name
                t_in.dStart = start_time
                t_in.dFinish = start_time + datetime.timedelta(hours=float(task.Estimate))
                max_st_end_time = max(max_end_time, t_in.dFinish)

                # look for resource
                resource_id = None
                for r_id, resource in self.resources.items():
                    if resource == task.Owner.Name:
                        resource_id = r_id
                        break
                if not resource_id:
                    resource_id = len(self.resources) + 1
                    self.resources[resource_id] = str(task.Owner.Name)

                t_in.resource = resource_id

                t.tasks.append(t_in)
            print ''
            t.dFinish = max_st_end_time
            max_end_time = max(max_end_time, t.dFinish)
            self.tasks.append(t)

        self.dFinish = max_end_time

    # Schedule
    def export_schedule(self, out_file):
        raise Exception('decide what to do')
