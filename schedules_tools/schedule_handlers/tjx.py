import datetime
import logging
import os

from lxml import etree

from schedules_tools import models, SchedulesToolsException
from schedules_tools.schedule_handlers import (ScheduleHandlerBase,
                                               TJXCommonMixin,
                                               )

log = logging.getLogger(__name__)


class TJXImportException(SchedulesToolsException):
    pass


class ScheduleHandler_tjx(TJXCommonMixin, ScheduleHandlerBase):
    provide_changelog = True

    handle_deps_satisfied = True

    @classmethod
    def is_valid_source(cls, handle=None):
        if not handle:
            handle = cls.handle
        file_ext = os.path.splitext(handle)[1]

        if file_ext == '.tjx':
            try:
                tree = etree.parse(handle)
            except etree.XMLSyntaxError:
                return False

            if tree.xpath('//Project[@Id and @WeekStart]'):
                return True
        return False

    def import_schedule(self):
        if not self.__class__.is_valid_source(self.handle):
            raise TJXImportException('Invalid TJX source', source=self.handle)

        self.schedule = models.Schedule()

        tree = self._get_parsed_tree()

        self.schedule.name = '%s %s' % (tree.xpath('Name')[0].text.strip(),
                                        tree.xpath('Version')[0].text)

        slug = str(tree.xpath('@Id')[0])
        if slug:
            self.schedule.slug = slug

        # look for same id as project, there might be more included root tasks
        eRoot_task = None
        eRoot_tasks = tree.xpath('Task[@Id = /Project/@Id]')
        if not len(eRoot_tasks):  # try whatever single root task
            eRoot_tasks = tree.xpath('Task')
            root_tasks_count = len(eRoot_tasks)
            if root_tasks_count == 1:
                eRoot_task = eRoot_tasks[0]
            elif root_tasks_count == 0:
                log.warning('Empty schedule %s ' % (self.handle,))
        else:
            eRoot_task = eRoot_tasks[0]

        if eRoot_task is not None:
            root_task_name = eRoot_task.xpath('Name')
            if root_task_name:
                self.schedule.name = root_task_name[0].text
        else:
            log.info('Can\'t find single root task in {} (found {} root '
                     'tasks)'.format(self.handle, len(eRoot_tasks)))

        self.schedule.name = self.schedule.name.strip()

        # import changelog/mtime from content of TJX
        self.schedule.changelog = self.get_handle_changelog()
        self.schedule.mtime = self.get_handle_mtime()

        min_date = datetime.datetime.max
        max_date = datetime.datetime.min

        for eTask in eRoot_tasks:
            task = models.Task(self.schedule, level=1)
            t_min_date, t_max_date = self.task_load_tjx_node(task, eTask)
            min_date = min(min_date, t_min_date)
            max_date = max(max_date, t_max_date)
            self.schedule.tasks.append(task)

        if self.schedule.tasks:
            self.schedule.dStart = min_date
            self.schedule.dFinish = max_date
            self.schedule.check_top_task()
        else:
            # try to load dates from project level
            start = self._load_tjx_date(tree, 'start')
            if start:
                self.schedule.dStart = start
            end = self._load_tjx_date(tree, 'end')
            if end:
                self.schedule.dFinish = end

        return self.schedule

    @staticmethod
    def _load_tjx_date(eTask, datetype, what=''):
        """Returns datetime with datetype = plan|actual what = start|end"""
        tag = datetype.lower() + what.capitalize()
        eTag = eTask.xpath(tag)
        if eTag:
            return datetime.datetime.fromtimestamp(float(eTag[0].text))

    def task_load_tjx_node(self, task, eTask):
        task.index = int(eTask.xpath('Index')[0].text)
        task.slug = eTask.get('Id')
        task.name = eTask.xpath('Name')[0].text.strip()

        notes = eTask.xpath('Note')
        if notes:
            task.note = notes[0].text.strip()

        task.priority = int(eTask.xpath('Priority')[0].text)
        task.p_complete = float(eTask.xpath('complete')[0].text)
        task.dStart = self._load_tjx_date(eTask, 'actual', 'start') or self._load_tjx_date(eTask, 'plan', 'start')
        task.dFinish = self._load_tjx_date(eTask, 'actual', 'end') or self._load_tjx_date(eTask, 'plan', 'end')

        # sanity check - if only tart defined and beyond plan finish
        task.dFinish = max(task.dFinish, task.dStart)
        task.milestone = eTask.xpath('Type')[0].text == 'Milestone'

        for eFlag in eTask.xpath('./Flag'):
            task.flags.append(eFlag.text)

        task._schedule.used_flags |= set(task.flags)

        ptask_el = eTask.xpath('./custom[@id="PTask"]')
        if ptask_el:
            task.link = ptask_el[0].get('url')

        min_date = task.dStart
        max_date = task.dFinish

        for eSubTask in eTask.xpath('./SubTasks/Task'):
            task_item = models.Task(task._schedule, task.level + 1)
            t_min_date, t_max_date = self.task_load_tjx_node(task_item,
                                                             eSubTask)
            min_date = min(min_date, t_min_date)
            max_date = max(max_date, t_max_date)

            task.tasks.append(task_item)

        return min_date, max_date
