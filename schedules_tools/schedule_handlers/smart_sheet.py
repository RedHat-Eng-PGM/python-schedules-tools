from schedules_tools.schedule_handlers import ScheduleHandlerBase
from schedules_tools import models
from smartsheet import Smartsheet

COLUMN_TASK_NAME = 'name'
COLUMN_DURATION = 'duration'
COLUMN_START = 'start'
COLUMN_ACSTART = 'acstart'
COLUMN_FINISH = 'finish'
COLUMN_ACFINISH = 'acfinish'
COLUMN_P_COMPLETE = 'complete'
COLUMN_NOTE = 'note'
COLUMN_FLAGS = 'note'
COLUMN_LINK = 'link'
COLUMN_PRIORITY = 'priority'


class ScheduleHandler_smartsheet(ScheduleHandlerBase):
    provide_export = False
    _client_instance = None
    _sheet_instance = None
    columns_mapping_name = {
        COLUMN_TASK_NAME: 'Task Name',
        COLUMN_DURATION: 'Duration',
        COLUMN_START: 'Start',
        COLUMN_FINISH: 'Finish',
        COLUMN_P_COMPLETE: '% Complete',
        COLUMN_NOTE: 'Comments',
        COLUMN_FLAGS: 'Flags',
        COLUMN_LINK: 'Link',
        COLUMN_ACSTART: 'Actual Start',
        COLUMN_ACFINISH: 'Actual Finish',
        COLUMN_PRIORITY: 'Priority',
    }
    columns_mapping_id = {}

    rows_registry = {}

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
            self._sheet_instance = self.client.get_sheet(self.handle)
        return self._sheet_instance

    def get_handle_mtime(self):
        return self.sheet.modifiedAt

    def import_schedule(self):
        sheet = self.client.get_sheet(self.handle)
        schedule = models.Schedule()
        parents_stack = []

        for row in sheet.rows:
            self._load_task(row, parents_stack, schedule)

    def _load_task(self, row, parents_stack, schedule):
        task = models.Task(schedule)
        self.rows_registry[row.id] = task
        columns = self._load_task_columns()
        if not parents_stack:
            parents_stack.append(row.id)

        if row.parent_id != parents_stack[-1]:
            parents_stack.append(row.id)

        task.index = None
        #task.slug = None
        task.name = columns[COLUMN_TASK_NAME]
        task.note = columns[COLUMN_NOTE]
        #task.priority = columns[COLUMN_PRIORITY]
        task.dStart = columns[COLUMN_START]
        task.dFinish = columns[COLUMN_FINISH]
        #task.dAcStart = columns[COLUMN_ACSTART]
        #task.dAcFinish = columns[COLUMN_ACFINISH]
        #task.milestone = int(columns[COLUMN_DURATION]) == 0
        #task.p_complete = columns[COLUMN_P_COMPLETE]
        flags_str = columns[COLUMN_FLAGS].strip(' ,')
        for flag in flags_str.split(', '):
            task.flags.append(flag)
        task.level = len(parents_stack)
        #task.link
        #task.tasks
        return task

    def _load_task_columns(self, row):
        cells = {}

        for cell in row.cells:
            cell_name = self.columns_mapping_id.get(cell.column_id, None)
            if not cell_name:
                continue

            cells[cell_name] = cell.value

        return cells
