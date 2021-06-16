from collections import OrderedDict
import os
import re
from schedules_tools.schedule_handlers.smart_sheet import ScheduleHandler_smartsheet
import yaml


DEFAULT_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
DEPENDENCY_REGEX = re.compile(r'^{(?P<to>predecessor|\d+)}(?P<type>[F|S]+)?'
                              r'( ?(?P<lag_sign>[+|-])?(?P<lag_amount>\d+)'
                              r'(?P<lag_type>[d|w]))?$')


def load_template(template_name):
    template_dir = os.getenv('BATCHES_TEMPLATE_DIR', DEFAULT_TEMPLATE_DIR)
    template_path = os.path.join(template_dir, '%s.yml' % template_name)

    if not os.path.exists(template_path):
        raise ValueError('Template "%s" now found.', template_name)

    with open(template_path, 'r') as f:
        template = yaml.safe_load(f)

    tasks = OrderedDict()
    for task in template['tasks']:
        task_id = task.pop('id')
        if 'dependency' in task:
            dependency_match = DEPENDENCY_REGEX.match(task['dependency'])
            if not dependency_match:
                raise ValueError('Incorrect dependency format: %s' % task['dependency'])
            else:
                task['dependency'] = dependency_match.groupdict()
        tasks[task_id] = task

    template['tasks'] = tasks

    return template


def initialize_ss_handler(handle):
    api_token = os.getenv('SMARTSHEET_TOKEN')

    if not api_token:
        raise ValueError('SMARTSHEET_TOKEN required')

    handler = ScheduleHandler_smartsheet(
        handle=handle,
        options={'smartsheet_token': api_token}
    )
    return handler
