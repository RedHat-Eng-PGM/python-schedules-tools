from schedules_tools import models
import datetime


def create_test_schedule():
    sch = models.Schedule()
    sch.dStart = datetime.datetime(2016, 12, 1, 8, 0)
    sch.dFinish = datetime.datetime(2016, 12, 22, 8, 0)
    sch.name = 'Schedules tools'
    sch.used_flags = set(['qe', 'pm', 'dev'])
    sch.slug = 'scht'

    task1 = models.Task(sch)
    task1.name = 'Schedules tools 1.0.0'
    task1.slug = 'scht'
    task1.dStart = datetime.datetime(2016, 12, 1, 8, 0)
    task1.dFinish = datetime.datetime(2016, 12, 20, 8, 0)
    task1.note = 'top task'
    task1.priority = 13
    task1.p_complete = 0
    sch.tasks.append(task1)

    task2 = models.Task(sch, level=task1.level + 1)
    task2.name = 'Planning'
    task2.slug = 'scht.plan'
    task2.dStart = datetime.datetime(2016, 12, 2, 8, 0)
    task2.dFinish = datetime.datetime(2016, 12, 4, 8, 0)
    task2.note = 'plan task'
    task2.priority = 34
    task2.p_complete = 10
    task2.flags = ['pm']
    task2.link = 'https://www.redhat.com'
    task1.tasks.append(task2)

    task3 = models.Task(sch, level=task1.level + 1)
    task3.name = 'Development'
    task3.slug = 'scht.dev'
    task3.dStart = datetime.datetime(2016, 12, 5, 8, 0)
    task3.dFinish = datetime.datetime(2016, 12, 15, 8, 0)
    task3.note = 'devel task'
    task3.priority = 100
    task3.p_complete = 90
    task3.flags = ['dev']
    task3.milestone = 'dev-milestone'
    task1.tasks.append(task3)

    task4 = models.Task(sch, level=task3.level + 1)
    task4.name = 'Handlers'
    task4.slug = 'scht.dev.handlers'
    task4.dStart = datetime.datetime(2016, 12, 10, 8, 0)
    task4.dFinish = datetime.datetime(2016, 12, 12, 8, 0)
    task4.priority = 100
    task4.p_complete = 123
    task4.flags = ['dev', 'qe']
    task3.tasks.append(task4)

    return sch
