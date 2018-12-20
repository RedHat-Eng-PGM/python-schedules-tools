import os
import tempfile
import logging

from datetime import datetime
from datetime import timedelta
from lxml import etree

from schedules_tools import models, SchedulesToolsException
from schedules_tools.schedule_handlers import ScheduleHandlerBase


MSP_FLAGS_ATTRS = ('Flags', )
datetime_format = '%Y-%m-%dT%H:%M:%S'

log = logging.getLogger(__name__)


class MSPImportException(SchedulesToolsException):
    pass


class ScheduleHandler_msp(ScheduleHandlerBase):
    provide_export = True

    handle_deps_satisfied = True
    
    default_export_ext = 'xml'

    # amount of working hours per day
    working_hours = 8

    @classmethod
    def is_valid_source(cls, handle=None):
        if not handle:
            handle = cls.handle
        try:
            tree = etree.parse(handle)
        except (etree.XMLSyntaxError, IOError):
            return False

        if 'http://schemas.microsoft.com/project' in tree.getroot().tag:
            return True
        return False

    # Schedule
    def import_schedule(self):
        self.schedule = models.Schedule()

        try:
            # remove project's xmlns
            tmp_file = tempfile.mkstemp()[1]
            with open(tmp_file, 'wt') as hTmp_file:
                for line in open(self.handle):
                    hTmp_file.write(line.replace(' xmlns="http://schemas.microsoft.com/project"', ''))
    
            start_level = 1
            tree = etree.parse(tmp_file)
    
            eTask_list = tree.xpath('Tasks/Task[OutlineLevel >= %s]' % start_level)
            self.schedule.name = tree.xpath('Name|Title')[0].text.strip()
            self.schedule.slug = self.schedule.unique_id_re.sub('_', self.schedule.name)
    
            # extended attributes
            for eExtAttr in tree.xpath('ExtendedAttributes/ExtendedAttribute'):
                fieldID = int(eExtAttr.xpath('FieldID')[0].text)
                fieldName = eExtAttr.xpath('FieldName')[0].text
                self.schedule.ext_attr[fieldName] = fieldID
    
            if self.schedule.ext_attr:  # choose flags field
                for ff_name in MSP_FLAGS_ATTRS:
                    if ff_name in self.schedule.ext_attr:
                        self.schedule.flags_attr_id = self.schedule.ext_attr[ff_name]
                        break
    
            self.schedule.tasks = self._load_tasks_level(start_level, eTask_list)
    
            os.unlink(tmp_file)
            self.schedule.check_top_task()
            self.schedule.generate_slugs()
            return self.schedule
        except etree.XMLSyntaxError as e:
            raise MSPImportException(e, source=self.handle)

    # Schedule
    def export_schedule(self, out_file=None):
        MSP_NAMESPACE = "http://schemas.microsoft.com/project"
        MSP = "{%s}" % MSP_NAMESPACE

        NSMAP = {None: MSP_NAMESPACE}  # the default namespace (no prefix)

        eProject = etree.Element(MSP + 'Project', nsmap=NSMAP)
        eName = etree.SubElement(eProject, 'Name')
        eName.text = self.schedule.name
        eTitle = etree.SubElement(eProject, 'Title')
        eTitle.text = self.schedule.name
        eMinutesPerDay = etree.SubElement(eProject, 'MinutesPerDay')
        working_minutes_per_day = self.working_hours * 60
        eMinutesPerDay.text = str(working_minutes_per_day)
        eMinutesPerWeek = etree.SubElement(eProject, 'MinutesPerWeek')
        # 7 working days
        eMinutesPerWeek.text = str(working_minutes_per_day * 7)

        calendar_UID = '1'
        # add ext condition
        eCalendarUID = etree.SubElement(eProject, 'CalendarUID')
        eCalendarUID.text = calendar_UID
        eCalendars = etree.SubElement(eProject, 'Calendars')
        eCalendar = etree.SubElement(eCalendars, 'Calendar')
        eUID = etree.SubElement(eCalendar, 'UID')
        eUID.text = calendar_UID
        eName = etree.SubElement(eCalendar, 'Name')
        eName.text = 'Standard'
        eIsBaseCalendar = etree.SubElement(eCalendar, 'IsBaseCalendar')
        eIsBaseCalendar.text = '1'
        eWeekDays = etree.SubElement(eCalendar, 'WeekDays')
        for day_type in range(1, 8):
            eWeekDay = etree.SubElement(eWeekDays, 'WeekDay')
            eDayType = etree.SubElement(eWeekDay, 'DayType')
            eDayType.text = str(day_type)
            eDayWorking = etree.SubElement(eWeekDay, 'DayWorking')
            eDayWorking.text = '1'
            eWorkingTimes = etree.SubElement(eWeekDay, 'WorkingTimes')

            # Sunday and Saturday don't have specified working hours
            if day_type in [1, 7]:
                continue

            for from_time in [(9, 3), (13, 5)]:
                eWorkingTime = etree.SubElement(eWorkingTimes, 'WorkingTime')
                eFromTime = etree.SubElement(eWorkingTime, 'FromTime')
                eFromTime.text = '%02d:00:00' % int(from_time[0])
                eToTime = etree.SubElement(eWorkingTime, 'ToTime')
                eToTime.text = '%02d:00:00' % (from_time[0] + from_time[1],)

        for r_id, resource in self.schedule.resources.items():
            eCalendar = etree.SubElement(eCalendars, 'Calendar')
            eUID = etree.SubElement(eCalendar, 'UID')
            eUID.text = str(r_id + 1)
            eName = etree.SubElement(eCalendar, 'Name')
            eName.text = resource
            eIsBaseCalendar = etree.SubElement(eCalendar, 'IsBaseCalendar')
            eIsBaseCalendar.text = '0'
            eBaseCalendarUID = etree.SubElement(eCalendar, 'BaseCalendarUID')
            eBaseCalendarUID.text = calendar_UID

        # SmartSheet workaround:
        # It's necessary to define at least one non-working days, due bug
        # in SmartSheet import, otherwise whole calendar is ignored..
        eExceptions = etree.SubElement(eCalendar, 'Exceptions')
        eException = etree.SubElement(eExceptions, 'Exception')
        eTimePeriod = etree.SubElement(eException, 'TimePeriod')
        eFromDate = etree.SubElement(eTimePeriod, 'FromDate')
        eToDate = etree.SubElement(eTimePeriod, 'ToDate')
        # use date 5y before whole schedule beginning
        exception_from_date = self.schedule.dStart.replace(
            year=self.schedule.dStart.year - 5)
        exception_to_date = exception_from_date + timedelta(days=1)
        eFromDate.text = exception_from_date.strftime(datetime_format)
        eToDate.text = exception_to_date.strftime(datetime_format)
        eType = etree.SubElement(eException, 'Type')
        eType.text = '1'

        eTasks = etree.SubElement(eProject, 'Tasks')
        self.export_msp_tasks(self.schedule.tasks, eTasks, '')

        eResources = etree.SubElement(eProject, 'Resources')
        for r_id, resource in self.schedule.resources.items():
            eResource = etree.SubElement(eResources, 'Resource')

            eUID = etree.SubElement(eResource, 'UID')
            eUID.text = str(r_id)

            eID = etree.SubElement(eResource, 'ID')
            eID.text = str(r_id)

            eName = etree.SubElement(eResource, 'Name')
            eName.text = resource

            eCalendarUID = etree.SubElement(eResource, 'CalendarUID')
            eCalendarUID.text = str(r_id + 1)

        eAssignments = etree.SubElement(eProject, 'Assignments')
        for assignment in self.schedule.assignments:
            eAssignment = etree.SubElement(eAssignments, 'Assignment')

            eTaskUID = etree.SubElement(eAssignment, 'TaskUID')
            eTaskUID.text = str(assignment['t_id'])

            eResourceUID = etree.SubElement(eAssignment, 'ResourceUID')
            eResourceUID.text = str(assignment['r_id'])

            eUnits = etree.SubElement(eAssignment, 'Units')
            eUnits.text = '1'

        et = etree.ElementTree(eProject)
        
        if out_file:
            et.write(out_file, pretty_print=True, encoding="utf-8",
                     xml_declaration=True)
        
        return str(et)        

    # Schedule
    def export_msp_tasks(self, tasks, eParent, outline_prefix):
        for n, task in enumerate(tasks, start=1):
            eTask = self.task_export_msp_node(task)
            eUID = etree.SubElement(eTask, 'UID')
            eUID.text = str(self.schedule._task_index)

            eID = etree.SubElement(eTask, 'ID')
            eID.text = str(self.schedule._task_index)

            if task.resource:
                self.schedule.assignments.append({
                    't_id': self.schedule._task_index,
                    'r_id': task.resource}
                )

            eOutlineNumber = etree.SubElement(eTask, 'OutlineNumber')
            eOutlineNumber.text = '%s%s' % (outline_prefix, n)

            eOutlineLevel = etree.SubElement(eTask, 'OutlineLevel')
            eOutlineLevel.text = str(len(outline_prefix.split('.')))

            eParent.append(eTask)

            self.schedule._task_index += 1
            self.export_msp_tasks(task.tasks, eParent,
                                  '%s.' % eOutlineNumber.text)

    # Schedule
    def _load_tasks_level(self, level, eTask_list):
        return_tasks = []

        while eTask_list:
            eTask = eTask_list[0]
            task_level = int(eTask.xpath('OutlineLevel')[0].text)

            if task_level > level:
                # return tasks may be empty since there could be no importable tasks yet
                if len(return_tasks):
                    return_tasks[-1].tasks = self._load_tasks_level(
                        task_level, eTask_list)
                else:
                    # remove task from list
                    eTask_list.pop(0)
                continue
            elif task_level < level:
                return return_tasks

            # process task
            task = models.Task(self.schedule, level=level)
            if self.task_load_msp_node(task, eTask):                
                # update schedule start/end
                if self.schedule.dStart:
                    self.schedule.dStart = min(self.schedule.dStart, task.dStart)
                else:
                    self.schedule.dStart = task.dStart

                if self.schedule.dFinish:
                    self.schedule.dFinish = max(self.schedule.dFinish, task.dFinish)
                else:
                    self.schedule.dFinish = task.dFinish
                    
                return_tasks.append(task)
            # remove task from list
            eTask_list.pop(0)
        return return_tasks

    # Task
    def task_load_msp_node(self, task, eTask):
        task.index = int(eTask.xpath('ID')[0].text)

        task.name = task._workaround_it_phase_names(eTask)
        if not task.name:
            return False

        task.priority = int(eTask.xpath('Priority')[0].text)

        nlStart = eTask.xpath('Start')

        if nlStart:
            task.dStart = datetime.strptime(nlStart[0].text,
                                            task._date_format)
            task.dFinish = task.dStart
        else:
            return False

        nlFinish = eTask.xpath('Finish')
        if nlFinish:
            task.dFinish = datetime.strptime(
                nlFinish[0].text,
                task._date_format
            )

        nlAcStart = eTask.xpath('ActualStart')
        if nlAcStart:
            task.dStart = datetime.strptime(nlAcStart[0].text,
                                            task._date_format)

        nlAcFinish = eTask.xpath('ActualFinish')
        if nlAcFinish:
            task.dFinish = datetime.strptime(nlAcFinish[0].text,
                                             task._date_format)

        # sanity check - if only start defined and beyond plan finish
        task.dFinish = max(task.dFinish, task.dStart)

        task.milestone = eTask.xpath('Milestone')[0].text == '1'

        ePercentComplete_list = eTask.xpath('PercentComplete')
        if ePercentComplete_list:
            task.p_complete = float(eTask.xpath('PercentComplete')[0].text)

        notes = eTask.xpath('Notes')
        if notes:
            task.note = notes[0].text.strip()

        # load flags from ext attributes
        flag_ext_attr = eTask.xpath(
            'ExtendedAttribute[FieldID = {}]'.format(
                task._schedule.flags_attr_id)
        )
        if flag_ext_attr:
            flags_value = flag_ext_attr[0].xpath('Value')[0].text
            if flags_value:
                task.flags = [f for f in flags_value.strip(' ,\n').split(',') if ' ' not in f]
                task._schedule.used_flags |= set(task.flags)

        # workaround for SmartSheet exports - load flags, links
        # @param value: XPath element instance (/Project/Tasks/Task/ExtendedAttribute/Value)
        ext_attr_elements = eTask.xpath('ExtendedAttribute/Value')
        for ext_attr in ext_attr_elements:
            task.parse_extended_attr(ext_attr.text)
        return True

    # Task
    def task_export_msp_node(self, task):
        eTask = etree.Element('Task')

        eName = etree.SubElement(eTask, 'Name')
        eName.text = task.name

        eStart = etree.SubElement(eTask, 'Start')
        eStart.text = task.dStart.strftime(datetime_format)
        eFinish = etree.SubElement(eTask, 'Finish')
        eFinish.text = task.dFinish.strftime(datetime_format)

        ePriority = etree.SubElement(eTask, 'Priority')
        ePriority.text = str(task.priority)

        # valid content is 0 or 1, not 'True', 'False'
        eMilestone = etree.SubElement(eTask, 'Milestone')
        eMilestone.text = str(int(task.milestone))

        duration = task.dFinish - task.dStart
        # Workaround for SmartSheet import:
        # They consider duration always +1 greater, than is difference between
        # finish and start date in whole days, Finish element is ignored by them
        duration += timedelta(days=1)
        eDuration = etree.SubElement(eTask, 'Duration')
        h, rem = divmod(duration.seconds, 3600)
        h += duration.days * self.working_hours
        m, s = divmod(rem, 60)
        eDuration.text = 'PT%sH%sM%sS' % (h, m, s)
        eDurationFormat = etree.SubElement(eTask, 'DurationFormat')
        eDurationFormat.text = '39'

        if task.note:
            eNotes = etree.SubElement(eTask, 'Notes')
            eNotes.text = task.note

        flags_str = ','.join(task.flags)
        if flags_str:
            ext_attr_element = etree.SubElement(eTask, 'ExtendedAttribute')
            value_element = etree.SubElement(ext_attr_element, 'Value')
            value_element.text = '{}: {}'.format(models.ATTR_PREFIX_FLAG, flags_str)

            # this value is not used, but required by SmartSheets import
            fieldid_element = etree.SubElement(ext_attr_element, 'FieldID')
            fieldid_element.text = '188743734'
        if task.link:
            ext_attr_element = etree.SubElement(eTask, 'ExtendedAttribute')
            value_element = etree.SubElement(ext_attr_element, 'Value')
            value_element.text = '{}: {}'.format(models.ATTR_PREFIX_LINK, task.link)

            # this value is not used, but required by SmartSheets import
            fieldid_element = etree.SubElement(ext_attr_element, 'FieldID')
            fieldid_element.text = '188743737'

        return eTask
