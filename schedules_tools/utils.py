import re
from copy import copy
from operator import attrgetter

TASK_SLUG_REGEX = re.compile(r'[\W_]+')


def sort_tasks(tasks, field):
    sort_key = attrgetter(field)
    return _sort_tasks(tasks, sort_key)


def _sort_tasks(tasks, key):
    tasks_copy = copy(tasks)

    sorted_tasks = sorted(
        tasks_copy,
        key=key
    )

    for task in sorted_tasks:
        task.tasks = _sort_tasks(copy(task.tasks), key)

    return sorted_tasks


def slugify(name):
    return TASK_SLUG_REGEX.sub('_', name.lower())
