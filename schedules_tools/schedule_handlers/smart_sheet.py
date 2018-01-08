from schedules_tools.schedule_handlers import ScheduleHandlerBase
from schedules_tools import models
import logging
import datetime
import re


COLUMN_TASK_NAME = 'name'
COLUMN_DURATION = 'duration'
COLUMN_START = 'start'
COLUMN_ACSTART = 'acstart'
COLUMN_FINISH = 'finish'
COLUMN_ACFINISH = 'acfinish'
COLUMN_P_COMPLETE = 'complete'
COLUMN_NOTE = 'note'
COLUMN_FLAGS = 'flags'
COLUMN_LINK = 'link'
COLUMN_PRIORITY = 'priority'

log = logging.getLogger(__name__)

smartsheet_logger = logging.getLogger('smartsheet.smartsheet')
smartsheet_logger.setLevel(logging.INFO)

try:
    from smartsheet import Smartsheet
    additional_deps_satistifed = True
except ImportError:
    additional_deps_satistifed = False


class ScheduleHandler_smartsheet(ScheduleHandlerBase):
    provide_export = True
    handle_deps_satisfied = additional_deps_satistifed

    date_format = '%Y-%m-%dT%H:%M:%S'  # 2017-01-20T08:00:00
    _client_instance = None
    _sheet_instance = None
    _re_number = re.compile('[0-9]+')
    columns_mapping_name = {
        'Task Name': COLUMN_TASK_NAME,
        'Duration': COLUMN_DURATION,
        'Start': COLUMN_START,
        'Finish': COLUMN_FINISH,
        '% Complete': COLUMN_P_COMPLETE,
        'Comments': COLUMN_NOTE,
        'Flags': COLUMN_FLAGS,
        'Link': COLUMN_LINK,
        'Actual Start': COLUMN_ACSTART,
        'Actual Finish': COLUMN_ACFINISH,
        'Priority': COLUMN_PRIORITY,
    }

    columns_mapping_id = {}

    def __init__(self, *args, **kwargs):
        super(ScheduleHandler_smartsheet, self).__init__(*args, **kwargs)

    @classmethod
    def is_valid_source(cls, handle=None):
        if not handle:
            handle = cls.handle
        try:
            int(handle)
        except ValueError:
            return False

        return True

    @property
    def client(self):
        if not self._client_instance:
            self._client_instance = Smartsheet(self.options['smartsheet_token'])
            self._client_instance.errors_as_exceptions(True)
        return self._client_instance

    @property
    def sheet(self):
        if not self._sheet_instance:
            self._sheet_instance = self.client.Sheets.get_sheet(self.handle)
        return self._sheet_instance

    def get_handle_mtime(self):
        return self.sheet.modified_at

    def import_schedule(self):
        self.schedule = models.Schedule()
        self.schedule.name = str(self.sheet.name)
        self.schedule.slug = str(self.schedule.unique_id_re.sub('_', self.schedule.name))
        self.schedule.mtime = self.get_handle_mtime()
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

        self.schedule.check_top_task()
        self.schedule.dStart = self.schedule.tasks[0].dStart
        self.schedule.dFinish = self.schedule.tasks[0].dFinish
        self.schedule.generate_slugs()
        return self.schedule

    def _parse_date(self, string):
        date = datetime.datetime.strptime(string, self.date_format)
        # We don't require so precise timestamp, so ignore seconds
        date = date.replace(second=0)
        return date

    def _load_task(self, row, parents_stack):
        task = models.Task(self.schedule)
        cells = self._load_task_cells(row)

        task.index = row.row_number
        # task.slug is generated at the end of importing whole schedule

        # skip empty rows
        if not cells[COLUMN_TASK_NAME]:
            return
        task.name = str(cells[COLUMN_TASK_NAME])

        if cells[COLUMN_NOTE]:
            task.note = str(cells[COLUMN_NOTE])
        if COLUMN_PRIORITY in cells:
            task.priority = cells[COLUMN_PRIORITY]

        task.dStart = self._parse_date(cells[COLUMN_START])
        task.dFinish = self._parse_date(cells[COLUMN_FINISH])
        if COLUMN_ACSTART in cells:
            task.dAcStart = cells[COLUMN_ACSTART]
        else:
            task.dAcStart = task.dStart

        if COLUMN_ACFINISH in cells:
            task.dAcFinish = cells[COLUMN_ACFINISH]
        else:
            task.dAcFinish = task.dFinish

        if COLUMN_DURATION in cells:
            # duration cell contains values like '14d', '~0'
            match = re.findall(self._re_number, cells[COLUMN_DURATION])
            if match:
                task.milestone = int(match[0]) == 0
        complete = cells[COLUMN_P_COMPLETE]
        if complete is not None:
            task.p_complete = round(complete * 100, 1)
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
            while row.parent_id != parents_stack[0]['rowid']:
                parents_stack.pop(0)
            parents_stack[0]['task'].tasks.append(task)
            parents_stack.insert(0, curr_stack_item)

        task.check_for_phase()
        task.level = len(parents_stack)

    def _load_task_cells(self, row):
        mapped_cells = {}

        for cell in row.cells:
            cell_name = self.columns_mapping_id.get(cell.column_id, None)
            if not cell_name:
                continue

            mapped_cells[cell_name] = cell.value

        return mapped_cells

    def export_schedule(self, output=None):
        sheet_spec = self.client.models.Sheet({
            'name': self.schedule.name,
            'from_id': 5066554783098756,
        })
        resp = self.client.Home.create_sheet_from_template(sheet_spec)
        self.handle = resp.result.id
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
        assert resp.message == 'SUCCESS'

        for task in self.schedule.tasks:
            self.export_task(task, parent_id=None)

        # sheet ID
        return self.handle

    @staticmethod
    def calculate_working_days_duration(dstart, dfinish):
        """
        Calculate number of days in starting and ending week.
        https://gist.github.com/archugs/bfbee2b8d210ca07c424#file-workingdaysusingloop-py

        Args:
            dstart: later date
            dfinish: sooner date

        Returns:
            number of working days between dstart and dfinish
        """
        all_days = [dstart + datetime.timedelta(days=x) for x in
                    range((dfinish - dstart).days + 1)]
        working_days = sum(1 for d in all_days if d.weekday() < 5)
        log.debug('duration: {} working days ({} - {})'.format(working_days,
                                                                  dstart,
                                                                  dfinish))
        return working_days

    def export_task(self, task, parent_id=None):
        row = self.client.models.Row()
        row.parent_id = parent_id
        row.to_bottom = True

        if task.name:
            row.cells.append({
                'column_id': self.sheet.columns[0].id,
                'value': task.name
            })
        if task.dStart:
            row.cells.append({
                'column_id': self.sheet.columns[2].id,
                'value': task.dStart.isoformat()
            })
        if task.milestone:
            row.cells.append({
                'column_id': self.sheet.columns[1].id,
                'value': '0'
            })
        elif task.dFinish:
            # finish date can be set only as (start, duration) tuple,
            # put direct value for Finish column is not allowed.
            duration = self.calculate_working_days_duration(task.dStart,
                                                            task.dFinish)
            row.cells.append({
                'column_id': self.sheet.columns[1].id,  # finish #3
                'value': '{}d'.format(duration)
            })
        if task.flags:
            row.cells.append({
                'column_id': self.sheet.columns[4].id,
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
        assert resp.message == 'SUCCESS', resp.result.message
        assert 1 == len(resp.result)

        row_id = resp.result[0].id

        for nested_task in task.tasks:
            self.export_task(nested_task, parent_id=row_id)

        return row_id
