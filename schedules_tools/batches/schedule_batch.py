#!/usr/bin/python3

# Test as "python -m schedules_tools.batches.schedule_batch"


import argparse
import re
from schedules_tools.batches.utils import initialize_ss_handler, load_template
from schedules_tools.models import Task

from smartsheet.models import Row, Cell, ObjectValue, PredecessorList, Predecessor, Duration


GA_NAME_REGEX = re.compile(r'^GA( Release)?$')
BATCH_NAME_REGEX = re.compile(r'^Batch update ([0-9]+)')


class BatchError(Exception):
    pass


def construct_task(name, duration=None):
    """
    makes an instance of schedule_tools Task
    """
    task = Task()
    task.name = name
    task.dStart = None
    task.dFinish = None
    if duration:
        task.duration = duration
    elif duration == 0:
        task.milestone = True

    return task


def build_columns_map(columns):
    result = {}

    for column in columns:
        if not column.title:
            continue

        column_name = column.title.lower()

        if column_name in ('task', 'task name'):
            result['name'] = column.index
        elif column_name in ('start', 'start date'):
            result['start'] = column.index
        elif column_name in ('finish', 'due', 'end date'):
            result['finish'] = column.index

    missing_columns = {'name', 'start', 'finish'} - set(result.keys())
    if missing_columns:
        raise BatchError(f'Couldn\'t locate required columns: {missing_columns}')

    return result


def add_batch(handle, template):
    handler = initialize_ss_handler(handle)
    columns_map = build_columns_map(handler.sheet.columns)
    parsed_rows = list(
        map(
            lambda x: parse_row(x, columns_map),
            handler.sheet.rows
        )
    )

    # finding relevant rows
    parent_row = find_parent_row(parsed_rows, template['parent'])
    if not parent_row:
        raise BatchError(f'Parent row "{template["parent"]}" not found.')

    if template.get('first'):
        predecessor_row = find_ga_row(parsed_rows)
        batch_number = 1
        batch_task_export_kwargs = {'to_top': True}
    else:
        latest_batch_row, latest_batch_number = find_latest_batch_row(
            parsed_rows,
            parent_row['id']
        )
        predecessor_row = find_predecessor_row_from_batch(
            parsed_rows,
            latest_batch_row['id'],
            template['predecessor-task-name']
        )
        batch_number = latest_batch_number + 1
        batch_task_export_kwargs = {'sibling_id': latest_batch_row['id']}

    batch_name = 'Batch update %d' % batch_number
    if 'type' in template:
        batch_name = '%s %s' % (batch_name, template['type'])

    # adding main batch task
    batch_task = construct_task(batch_name)
    batch_row_id = handler.export_task(
        batch_task,
        parent_id=parent_row['id'],
        **batch_task_export_kwargs
    ).id

    # exporting batch tasks and mapping them to set dependencies later
    # can't set dependencies right away because task
    # dependency might not be in the schedule yet
    task_id_to_row = {}
    for task_id, task_data in template['tasks'].items():
        st_task = construct_task(task_data['name'], duration=task_data['duration'])
        task_export_row = handler.export_task(st_task, batch_row_id)
        task_id_to_row[task_id] = parse_row(task_export_row, columns_map)

    # setting dependencies
    for task_id, task_data in template['tasks'].items():
        if 'dependency' not in task_data:
            continue

        pred_list = PredecessorList()
        pred = Predecessor()

        dependency_dict = task_data['dependency']
        if dependency_dict['to'] == 'predecessor':
            pred.row_id = predecessor_row['id']
        else:
            pred.row_id = task_id_to_row[int(dependency_dict['to'])]['id']
        pred.type = dependency_dict.get('type') or 'FS'
        if dependency_dict['lag_amount']:
            lag_duration = Duration()
            lag_duration.negative = dependency_dict['lag_sign'] == '-'
            lag_amount = int(dependency_dict['lag_amount'])
            if dependency_dict['lag_type'] == 'd':
                lag_duration.days = lag_amount
            else:
                lag_duration.weeks = lag_amount
            pred.lag = lag_duration

        pred_list.predecessors = [pred]

        dependency_cell = Cell()
        dependency_cell.column_id = handler._sheet_columns['predecessors']
        dependency_cell.object_value = ObjectValue()
        dependency_cell.object_value.object_type = "PREDECESSOR_LIST"
        dependency_cell.object_value = pred_list

        task_row = task_id_to_row[task_id]
        task_update_row = Row()
        task_update_row.id = task_row['id']
        task_update_row.cells.append(dependency_cell)

        handler.client.Sheets.update_rows(
            handler.handle,
            [task_update_row]
        )


def parse_row(row, columns_map):
    """
    converts smartsheet row into a dict
    """
    row_dict = row.to_dict()
    cells = row_dict['cells']
    result = {
        'id': row_dict['id'],
        'row_number': row_dict['rowNumber'],
        'parent_id': row_dict.get('parentId'),
        'name': cells[columns_map['name']].get('value'),
        'date_start': cells[columns_map['start']].get('value'),
        'date_finish': cells[columns_map['finish']].get('value'),
    }
    return result


def find_parent_row(parsed_rows, parent_name):
    """
    finds a parent row by a given name
    """
    for row in parsed_rows:
        task_name = row['name']
        if not task_name:
            continue

        if task_name == parent_name:
            return row

    return None


def find_latest_batch_row(parsed_rows, batch_parent_row_id):
    """
    finds latest batch in the schedule
    """
    children_rows = filter(
        lambda x: x['parent_id'] == batch_parent_row_id,
        parsed_rows
    )

    latest_batch_row = None
    latest_batch_number = None

    for row in children_rows:
        batch_regex_match = BATCH_NAME_REGEX.match(row['name'])

        if batch_regex_match:
            batch_number = int(batch_regex_match.groups()[0])
            if not latest_batch_number or batch_number > latest_batch_number:
                latest_batch_row = row
                latest_batch_number = batch_number

    return latest_batch_row, latest_batch_number


def find_predecessor_row_from_batch(parsed_rows, batch_row_id, predecessor_name):
    """
    finds a relevant predecessor row in a batch
    """
    batch_rows = filter(
        lambda x: x['parent_id'] == batch_row_id,
        parsed_rows
    )
    for row in batch_rows:
        if row['name'] == predecessor_name:
            return row

    return None


def find_ga_row(parsed_rows):
    """
    finds GA in the schedule
    """
    for row in parsed_rows:
        if GA_NAME_REGEX.match(row['name']):
            return row


def main():
    parser = argparse.ArgumentParser(
        description='Add a batch to SmartSheet schedule',
        epilog="""
Requires SmartSheet API token in SMARTSHEET_API_TOKEN env variable.
It's possible to use custom batch templates by specifying BATCHES_TEMPLATE_DIR env variable.
        """,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument('template',
                        help='template name)',
                        type=str,)
    parser.add_argument('handle',
                        help='SmartSheet handle (URL)',
                        type=str,)

    args = parser.parse_args()

    template = load_template(args.template)
    add_batch(args.handle, template)


if __name__ == '__main__':
    main()
