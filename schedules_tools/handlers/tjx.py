from schedules_tools.handlers import ScheduleHandlerBase, TJXChangelog
from schedules_tools import models
import datetime
import logging
import os
from lxml import etree

logger = logging.getLogger(__name__)

KNOWN_FLAGS = set([
    'team',

    'partner',
    'partner_hp',

    'interface',

    'roadmap',

    'hidden',

    'qe',
    'marketing',
    'pm',
    'security',
    'devel',
    'docs',
    'releng',
    'support',
    'training',
    'qertt',
    'it',
    'i18n',
    'certification',
    'prod',
    'sysops'
])

date_format = '%Y-%m-%d'
datetime_format_tz = '%Y-%m-%d %H:%M:%S EDT'


class ScheduleHandler_tjx(ScheduleHandlerBase, TJXChangelog):
    provide_export = True

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

    def get_handle_mtime(self):
        return self._get_mtime_from_handle_file()

    # Schedule
    def import_schedule(self):
        self.schedule = models.Schedule()

        tree = etree.parse(self.handle)
        project_name = tree.xpath('Name')[0].text.strip()
        self.schedule.name = '%s %s' % (project_name,
                                        tree.xpath('Version')[0].text)
        self.schedule.project_name = project_name
        proj_id = str(tree.xpath('@Id')[0])
        if proj_id:
            self.schedule.proj_id = proj_id

        # look for same id as project, 'cos there might be more included root tasks
        eRoot_task = None
        eRoot_tasks = tree.xpath('Task[@Id = /Projectget_unique_task_id/@Id]')
        if not len(eRoot_tasks):  # try whatever single root task
            eRoot_tasks = tree.xpath('Task')
            root_tasks_count = len(eRoot_tasks)
            if root_tasks_count == 1:
                eRoot_task = eRoot_tasks[0]
            elif root_tasks_count == 0:
                logger.warning('Empty schedule %s ' % (self.handle,))
        else:
            eRoot_task = eRoot_tasks[0]

        if eRoot_task is not None:
            root_task_name = eRoot_task.xpath('Name')
            if root_task_name:
                self.schedule.name = root_task_name[0].text
        else:
            logger.info('Can\'t find single root task in %s (found %d root tasks)' % (self.handle, len(eRoot_tasks)))

        self.schedule.name = self.schedule.name.strip()

        # import changelog, fill schedule.mtime
        if self.src_storage_handler:
            self.schedule.changelog = self.src_storage_handler.get_changelog(
                self.handle)
            self.schedule.mtime = self.src_storage_handler.get_mtime(self.handle)
        else:
            self.parse_changelog(tree)
            self.schedule.mtime = self.get_handle_changelog()

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

    # Task
    def task_export_tjx_node(self, task, id_prefix, proj_id):
        tj_id = task.tjx_id
        if not tj_id:
            tj_id = self.schedule.get_unique_task_id(task, id_prefix)

        eTask = etree.Element('Task', Id=tj_id)

        eIndex = etree.SubElement(eTask, 'Index')
        eIndex.text = str(task.index)

        eName = etree.SubElement(eTask, 'Name')
        eName.text = task.name

        eProjID = etree.SubElement(eTask, 'ProjectID')
        eProjID.text = proj_id

        ePriority = etree.SubElement(eTask, 'Priority')
        ePriority.text = str(task.priority)

        eComplete = etree.SubElement(eTask, 'complete')
        eComplete.text = str(task.p_complete)

        eType = etree.SubElement(eTask, 'Type')
        eType.text = task.get_type(check_same_start_finish=True)

        for flag in task.flags:
            eType = etree.SubElement(eTask, 'Flag')
            eType.text = flag

        if tj_id != id_prefix:  # not first task
            eParentTask = etree.SubElement(eTask, 'ParentTask')
            eParentTask.text = id_prefix

        if task.link:
            ptask = etree.SubElement(eTask, 'custom')
            ptask.attrib['id'] = 'PTask'
            ptask.attrib['url'] = task.link

        eActualStart = etree.SubElement(
            eTask,
            'actualStart',
            humanReadable=task.dAcStart.strftime(datetime_format_tz))
        eActualStart.text = task.dAcStart.strftime('%s')

        eActualEnd = etree.SubElement(
            eTask,
            'actualEnd',
            humanReadable=task.dAcFinish.strftime(datetime_format_tz))
        eActualEnd.text = task.dAcFinish.strftime('%s')

        ePlanStart = etree.SubElement(
            eTask,
            'planStart',
            humanReadable=task.dStart.strftime(datetime_format_tz))
        ePlanStart.text = task.dStart.strftime('%s')

        ePlanEnd = etree.SubElement(
            eTask,
            'planEnd',
            humanReadable=task.dFinish.strftime(datetime_format_tz))
        ePlanEnd.text = task.dFinish.strftime('%s')

        if task.note:
            eNote = etree.SubElement(eTask, 'Note')
            eNote.text = task.note

        if task.tasks:
            eSubTasks = etree.SubElement(eTask, 'SubTasks')
            for task in task.tasks:
                eSubTasks.append(self.task_export_tjx_node(
                    task,
                    tj_id,
                    proj_id))

        return eTask

    # Task
    @staticmethod
    def _load_tjx_date(eTask, datetype, what=''):
        """Returns datetime with datetype = plan|actual what = start|end"""
        tag = datetype.lower() + what.capitalize()
        eTag = eTask.xpath(tag)
        if eTag:
            return datetime.datetime.fromtimestamp(float(eTag[0].text))

    # Task
    def task_load_tjx_node(self, task, eTask):
        task.index = eTask.xpath('Index')[0].text
        task.tjx_id = eTask.get('Id')
        task.name = eTask.xpath('Name')[0].text.strip()

        notes = eTask.xpath('Note')
        if notes:
            task.note = notes[0].text.strip()

        task.priority = eTask.xpath('Priority')[0].text
        task.p_complete = eTask.xpath('complete')[0].text
        task.dStart = task.dAcStart = self._load_tjx_date(eTask, 'plan',
                                                          'start')
        task.dFinish = task.dAcFinish = self._load_tjx_date(eTask, 'plan',
                                                            'end')

        acStart = self._load_tjx_date(eTask, 'actual', 'start')
        if acStart:
            task.dAcStart = acStart
        acFinish = self._load_tjx_date(eTask, 'actual', 'end')
        if acFinish:
            task.dAcFinish = acFinish

        # sanity check - if only ac start defined and beyond plan finish
        task.dAcFinish = max(task.dAcFinish, task.dAcStart)
        task.milestone = eTask.xpath('Type')[0].text == 'Milestone'

        for eFlag in eTask.xpath('./Flag'):
            task.flags.append(eFlag.text)

        task._schedule.used_flags |= set(task.flags)

        ptask_el = eTask.xpath('./custom[@id="PTask"]')
        if ptask_el:
            task.link = ptask_el[0].get('url')

        min_date = task.dStart
        max_date = task.dAcFinish

        task.check_for_phase()

        for eSubTask in eTask.xpath('./SubTasks/Task'):
            task_item = models.Task(task._schedule, task.level + 1)
            t_min_date, t_max_date = self.task_load_tjx_node(task_item, eSubTask)
            min_date = min(min_date, t_min_date)
            max_date = max(max_date, t_max_date)

            task.tasks.append(task_item)

        return min_date, max_date

    # Schedule
    def export_schedule(self, out_file=None):
        eProject = etree.Element('Project', Id=self.schedule.proj_id,
                                 WeekStart='Mon')

        eName = etree.SubElement(eProject, 'Name')
        eName.text = self.schedule.project_name

        eVersion = etree.SubElement(eProject, 'Version')
        eVersion.text = self.schedule.version

        ePriority = etree.SubElement(eProject, 'Priority')
        ePriority.text = '500'

        eStart = etree.SubElement(
            eProject,
            'start',
            humanReadable=self.schedule.dStart.strftime(date_format))
        eStart.text = self.schedule.dStart.strftime('%s')

        eEnd = etree.SubElement(eProject, 'end',
                                humanReadable=self.schedule.dFinish.strftime(
                                    date_format))
        eEnd.text = self.schedule.dFinish.strftime('%s')

        now = datetime.datetime.now()
        eNow = etree.SubElement(eProject, 'now',
                                humanReadable=now.strftime(date_format))
        eNow.text = now.strftime('%s')

        self.schedule.id_reg = set()

        for item in self.schedule.tasks:
            eProject.append(self.task_export_tjx_node(item,
                                                      self.schedule.proj_id,
                                                      self.schedule.proj_id))

        et = etree.ElementTree(eProject)

        if out_file:
            et.write(out_file, pretty_print=True, encoding="utf-8",
                     xml_declaration=True)
        
        return str(et)
