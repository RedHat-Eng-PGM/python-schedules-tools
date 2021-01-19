import calendar
import datetime
import logging
import numbers
import re
import traceback

from schedules_tools.schedule_handlers import ScheduleHandlerBase
from schedules_tools import models, SchedulesToolsException


COLUMN_TASK_NAME = 'name'
COLUMN_DURATION = 'duration'
COLUMN_START = 'start'
COLUMN_FINISH = 'finish'
COLUMN_P_COMPLETE = 'complete'
COLUMN_NOTE = 'note'
COLUMN_FLAGS = 'flags'
COLUMN_LINK = 'link'
COLUMN_PRIORITY = 'priority'

log = logging.getLogger(__name__)


class SmartSheetImportException(SchedulesToolsException):
    pass


class SmartSheetExportException(SchedulesToolsException):
    pass


try:
    import smartsheet
    additional_deps_satistifed = True
except ImportError:
    additional_deps_satistifed = False


def date_range(start, finish):
    current_date = start
    while current_date != finish:
        yield current_date
        current_date += datetime.timedelta(days=1)
    yield finish


class ScheduleHandler_smartsheet(ScheduleHandlerBase):
    provide_export = True
    handle_deps_satisfied = additional_deps_satistifed

    date_format = '%Y-%m-%d'  # 2017-01-20
    datetime_format = '%Y-%m-%dT%H:%M:%S'  # 2017-01-20T08:00:00
    _client_instance = None
    _sheet_instance = None
    _sheet_columns = None
    _re_number = re.compile(r'[0-9]+')
    _re_url = re.compile(r'^(https?://.*?smartsheet.com[^?]+)')
    columns_mapping_name = {
        'Task': COLUMN_TASK_NAME,
        'Task Name': COLUMN_TASK_NAME,
        'Duration': COLUMN_DURATION,
        'Start': COLUMN_START,
        'Start Date': COLUMN_START,
        'Due': COLUMN_FINISH,
        'Finish': COLUMN_FINISH,
        'End Date': COLUMN_FINISH,
        '% Complete': COLUMN_P_COMPLETE,
        'Comments': COLUMN_NOTE,
        'Flags': COLUMN_FLAGS,
        'Link': COLUMN_LINK,
        'Priority': COLUMN_PRIORITY,
    }
    dayname_to_isoweekday = {x.lower(): i + 1 for i, x in enumerate(calendar.day_name)}

    columns_mapping_id = {}

    wrong_handles = set([])  # not existing handles cache

    # getter/setter to convert handle to Smartsheet id
    @property
    def handle(self):
        return self._handle

    @handle.setter
    def handle(self, value):
        self._handle = value

        # try to get id if not passed
        if value is not None and not ScheduleHandler_smartsheet.value_is_ss_id(
                                                                    value):
            info_dict = self.get_info_dict(value)

            if 'id' in info_dict:
                self._handle = info_dict['id']

    def get_info_dict(self, value):
        """Return dict with smarsheet id and permalink - get missing one"""

        info_dict = {}

        if ScheduleHandler_smartsheet.value_is_ss_id(value):
            try:
                sheet = self.client.Sheets.get_sheet(value)
                info_dict = dict(id=int(value), permalink=sheet.permalink)
            except smartsheet.exceptions.ApiError as e:
                log.warn(e)

        else:
            match = ScheduleHandler_smartsheet.value_is_ss_permalink(value)
            if match:
                value = match.groups()[0]

                # Need a speedup in case of wrong handle
                if value not in self.__class__.wrong_handles:
                    log.info('Getting sheets looking for handle (consuming)')
                    log.info('Waiting on Smartsheets')

                    sheets = self.client.Sheets.list_sheets(include_all=True)

                    log.info('Getting sheets looking for handle (consuming) - DONE')

                    for sheet in sheets.data:
                        if sheet.permalink == value:
                            info_dict = info_dict = dict(id=int(sheet.id),
                                                         permalink=value)
                            break

                    if not info_dict:
                        self.__class__.wrong_handles.add(value)

        return info_dict

    @classmethod
    def value_is_ss_id(cls, value):
        try:
            # looks like a sheet ID (number) - might be string
            int(value)
            return True
        except ValueError:
            pass

    @classmethod
    def value_is_ss_permalink(cls, value):
        return cls._re_url.match(str(value))

    @classmethod
    def is_valid_source(cls, handle=None):
        if not handle:
            handle = cls.handle

        return cls.value_is_ss_permalink(handle) or cls.value_is_ss_id(handle)

    @property
    def client(self):
        if not self._client_instance:
            self._client_instance = smartsheet.Smartsheet(
                self.options['smartsheet_token'])
            self._client_instance.errors_as_exceptions(True)
        return self._client_instance

    @property
    def sheet(self):
        if not self._sheet_instance:
            if self.handle in self.__class__.wrong_handles:
                raise SmartSheetImportException(
                    'Wrong handle (does not exist or missing permissions)', source=self.handle)
            try:
                # get sheet and turn off rows pagination to get all rows
                self._sheet_instance = self.client.Sheets.get_sheet(
                    self.handle, page_size=None, page=None)

            except smartsheet.exceptions.ApiError as e:
                raise SmartSheetImportException(e.message, source=self.handle)

        return self._sheet_instance

    @property
    def sheet_columns(self):
        if self._sheet_columns is None:
            self._sheet_columns = {x.title.lower(): x.id
                                   for x in self.sheet.columns}
        return self._sheet_columns

    @property
    def working_days_and_holidays(self):
        if not self._working_days_and_holidays:
            sheet = self.sheet
            verbose_working_weekdays = sheet.project_settings.working_days.to_list()
            working_isoweekdays = set(self.dayname_to_isoweekday[x.lower()]
                                      for x in verbose_working_weekdays)
            holidays = set(sheet.project_settings.working_days.non_working_days.to_list())
            self._working_days_and_holidays = working_isoweekdays, holidays

        return self._working_days_and_holidays

    def calculate_duration(self, start, finish):
        if start == finish:
            return 1

        working_isoweekdays, holidays = self.working_days_and_holidays
        duration = 1

        for date in date_range(start, finish):
            if date.isoweekday() not in working_isoweekdays:
                continue

            if date in holidays:
                continue

            duration += 1

        return duration

    def get_handle_mtime(self):
        return self.sheet.modified_at

    def get_handle_changelog(self):
        changelog = dict()

        changelog[self.sheet.version] = {
            'date': self.sheet.modified_at,
            'user': None,
            'msg': None,
        }

        return changelog

    def import_schedule(self):
        log.info('Import schedule %s' % self.handle)
        log.info('Waiting on Smartsheets')

        try:
            self.schedule = models.Schedule()
            self.schedule.name = str(self.sheet.name)
            self.schedule.slug = str(
                self.schedule.unique_id_re.sub('_', self.schedule.name))
            self.schedule.mtime = self.get_handle_mtime()
            self.schedule.changelog = self.get_handle_changelog()
            if self.options.get('trim_time'):
                self.schedule.dStart = datetime.date.max
                self.schedule.dFinish = datetime.date.min
            else:
                self.schedule.dStart = datetime.datetime.max
                self.schedule.dFinish = datetime.datetime.min
            log.debug('Import schedule - after first call to smartsheet')

            parents_stack = []

            # populate columns dict/map
            for column in self.sheet.columns:
                index = self.columns_mapping_name.get(column.title, None)
                if index is None:
                    log.debug('Unknown column %s, skipping.' % column.title)
                    continue
                self.columns_mapping_id[column.id] = index

            for row in self.sheet.rows:
                self._load_task(row, parents_stack)

            if not self.schedule.tasks:
                self.schedule.dStart = None
                self.schedule.dFinish = None
                log.warning('Empty schedule (no valid tasks) %s'
                            % self.get_info_dict(self.handle)['permalink'])

            self.schedule.generate_slugs()

        except (KeyError, IndexError):
            # We can get all exception details via traceback
            # instead of 'except' statement
            msg = traceback.format_exc()
            raise SmartSheetImportException(msg, source=self.handle)

        except smartsheet.exceptions.ApiError as e:
            raise SmartSheetImportException(e.message, source=self.handle)

        return self.schedule

    def _parse_date(self, date_str):
        """
        Method tries to parse date_str into python-native datetime object.

        Native smartsheet columns like 'Start' contains also time, but newly
        added columns via API aren't allowed to store time part.

        Args:
            date_str: Examples of input: 2017-01-20 or 2017-01-20T08:00:00

        Returns:
            datetime instance or None if string couldn't be parsed
        """
        date = None

        for format_str in [self.datetime_format, self.date_format]:
            try:
                date = datetime.datetime.strptime(date_str, format_str)
                break
            except ValueError:
                pass
        # We don't require so precise timestamp, so ignore seconds
        if date:
            date = date.replace(second=0)

        if date is not None and self.options.get('trim_time'):
            date = date.date()

        return date

    def _load_task(self, row, parents_stack):
        task = models.Task(self.schedule)
        cells, unknown_cells = self._load_task_cells(row)

        task.index = row.row_number
        # task.slug is generated at the end of importing whole schedule

        # skip empty rows
        if not all([c in cells and cells[c]
                    for c in (COLUMN_TASK_NAME, COLUMN_START, COLUMN_FINISH)]):
            # skip load, task doesn't contain all needed info
            return

        task.name = str(cells[COLUMN_TASK_NAME])

        # dates
        task.dStart = self._parse_date(cells[COLUMN_START])
        task.dFinish = self._parse_date(cells[COLUMN_FINISH])

        if not (task.dStart and task.dFinish):
            # Couldn't parse the dates
            return

        self.schedule.dStart = min(self.schedule.dStart, task.dStart)
        self.schedule.dFinish = max(self.schedule.dFinish, task.dFinish)

        if COLUMN_NOTE in cells and cells[COLUMN_NOTE]:
            task.note = str(cells[COLUMN_NOTE])

        if COLUMN_PRIORITY in cells:
            task.priority = cells[COLUMN_PRIORITY]

        if COLUMN_DURATION in cells:
            # duration cell contains values like '14d', '~0'
            match = re.findall(self._re_number, cells[COLUMN_DURATION])
            if match:
                task.milestone = int(match[0]) == 0

        if (COLUMN_P_COMPLETE in cells and cells[COLUMN_P_COMPLETE] is not None
                and isinstance(cells[COLUMN_P_COMPLETE], numbers.Number)):
            task.p_complete = round(cells[COLUMN_P_COMPLETE] * 100, 1)

        if COLUMN_FLAGS in cells and cells[COLUMN_FLAGS]:
            # try first to parse workaround format 'Flags: qe, dev'
            task.parse_extended_attr(cells[COLUMN_FLAGS])

            # then try to consider the value as it is 'qe, dev'
            if not task.flags:
                task.parse_extended_attr(cells[COLUMN_FLAGS],
                                         key=models.ATTR_PREFIX_FLAG)

        if COLUMN_LINK in cells and cells[COLUMN_LINK]:
            # try first to parse workaround format 'Link: http://some.url'
            task.parse_extended_attr(cells[COLUMN_LINK])
            # then try to consider the value as it is 'http://some.url'
            if not task.link:
                task.parse_extended_attr(cells[COLUMN_LINK],
                                         key=models.ATTR_PREFIX_LINK)
        # Try to guess column/purpose of unknown cell values
        for cell in unknown_cells:
            task.parse_extended_attr(cell)

        curr_stack_item = {
            'rowid': row.id,
            'task': task
        }

        if not parents_stack:
            # Current task is the topmost (root)
            self.schedule.tasks = [task]
            parents_stack.insert(0, curr_stack_item)

        elif row.parent_id == parents_stack[0]['rowid']:
            # Current task is direct descendant of latest task
            parents_stack[0]['task'].tasks.append(task)
            parents_stack.insert(0, curr_stack_item)

        elif row.parent_id != parents_stack[0]['rowid']:
            # We are currently in the same, or upper, level of tree
            while parents_stack and row.parent_id != parents_stack[0]['rowid']:
                parents_stack.pop(0)

            if parents_stack:
                parents_stack[0]['task'].tasks.append(task)
            else:
                self.schedule.tasks.append(task)

            parents_stack.insert(0, curr_stack_item)
        task.level = len(parents_stack)

    def _load_task_cells(self, row):
        """
        Method tries to combine expected column name together with cell value.
        Cell those don't match are returned back as list of values.

        Args:
            row: smartsheet Row instance

        Returns: tuple (mapped, unknown) cells, resp. unknown values

        """
        mapped_cells = {}
        unknown_values = []
        used_cells = set()

        for cell in row.cells:
            cell_name = self.columns_mapping_id.get(cell.column_id, None)
            if not cell_name:
                if cell.value is not None:
                    unknown_values.append(cell.value)
                continue
            # avoid to override existing values when column name is duplicated
            if cell_name not in used_cells and cell.value:
                mapped_cells[cell_name] = cell.value
                used_cells.add(cell_name)

        return mapped_cells, unknown_values

    def export_schedule(self, output=None):
        # Project sheet from API (Templates.list_public_templates)
        schedule_name = self.schedule.name[:50]

        sheet_spec = self.client.models.Sheet({
            'name': schedule_name,
            'from_id': 5066554783098756,
        })
        resp = self.client.Home.create_sheet_from_template(sheet_spec)
        self.handle = resp.result.id

        # mark whole week as working days to avoid 'rounding' duration
        # over weekends
        self.client.Sheets.update_sheet(
            self.handle,
            self.client.models.Sheet({
                'project_settings': self.client.models.ProjectSettings({
                    'working_days': [
                        'SUNDAY', 'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY',
                        'FRIDAY', 'SATURDAY']
                })
            })
        )

        column_spec_flags = self.client.models.Column({
            'title': 'Flags',
            'type': 'TEXT_NUMBER',
            'index': 4,
        })
        column_spec_link = self.client.models.Column({
            'title': 'Link',
            'type': 'TEXT_NUMBER',
            'index': 4,
        })
        resp = self.client.Sheets.add_columns(
            self.handle,
            [column_spec_flags, column_spec_link]
        )

        if resp.message != 'SUCCESS':
            msg = 'Adding column failed: {}'.format(resp)
            raise SmartSheetExportException(msg, source=self.handle)

        for task in self.schedule.tasks:
            self.export_task(task, parent_id=None)

        # sheet ID
        return self.handle

    def export_task(self, task, parent_id=None, sibling_id=None, to_top=False):
        row = self.client.models.Row()
        if sibling_id:
            row.sibling_id = sibling_id
        else:
            if to_top:
                row.to_top = True
            else:
                row.to_bottom = True
            if parent_id:
                row.parent_id = parent_id

        if task.name:
            row.cells.append({
                'column_id': self.sheet_columns['task name'],
                'value': task.name
            })
        if task.dStart:
            if isinstance(task.dStart, datetime.datetime):
                task.dStart = task.dStart.date()
            row.cells.append({
                'column_id': self.sheet_columns['start'],
                'value': task.dStart.isoformat()
            })
        if task.milestone:
            row.cells.append({
                'column_id': self.sheet_columns['duration'],
                'value': '0'
            })
        elif task.dFinish:
            # finish date can be set only as (start, duration) tuple,
            # put direct value for Finish column is not allowed.
            # Even if start and finish date are the same, duration equals 1.
            if isinstance(task.dFinish, datetime.datetime):
                task.dFinish = task.dFinish.date()
            duration = (task.dFinish - task.dStart).days + 1
            row.cells.append({
                'column_id': self._sheet_columns['duration'],
                'value': '{}d'.format(duration)
            })
        elif task.duration:
            row.cells.append({
                'column_id': self._sheet_columns['duration'],
                'value': '{}d'.format(task.duration)
            })

        if task.flags:
            row.cells.append({
                'column_id': self._sheet_columns['flags'],
                'value': ', '.join(task.flags)
            })
        if task.link:
            row.cells.append({
                'column_id': self.sheet.columns[5].id,
                'value': task.link
            })
        if task.p_complete:
            row.cells.append({
                'column_id': self.sheet.columns[8].id,
                'value': task.p_complete / 100.0
            })
        if task.note:
            row.cells.append({
                'column_id': self.sheet.columns[10].id,
                'value': task.note
            })
        resp = self.client.Sheets.add_rows(self.handle, [row])

        if resp.message != 'SUCCESS':
            raise SmartSheetExportException(resp.result.message,
                                            source=self.handle)
        len_result = len(resp.result)
        if 1 != len_result:
            msg = ('Just one row was expected to be added, instead '
                   'of {}'.format(len_result))
            raise SmartSheetExportException(msg, source=self.handle)

        row = resp.result[0]

        for nested_task in task.tasks:
            self.export_task(nested_task, parent_id=row.id)

        return row
