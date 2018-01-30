import logging
import json

from schedules_tools import jsondate
from schedules_tools.models import Task

log = logging.getLogger(__name__)


REPORT_NO_CHANGE = ''
REPORT_ADDED = '_added_'
REPORT_REMOVED = '_removed_'
REPORT_CHANGED = '_changed_'
# REPORT_NEW_VALUE = 'new_value'
# REPORT_OLD_VALUE = 'old_value'

REPORT_KEYS = {
    REPORT_ADDED,
    REPORT_REMOVED,
    REPORT_CHANGED,
}

REPORT_PREFIX_MAP = {
    REPORT_ADDED: '[+]',
    REPORT_REMOVED: '[-]',
    REPORT_CHANGED: '[M]',
    REPORT_NO_CHANGE: 3 * ' ',
}


class ScheduleDiff(object):

    result = []

    subtree_hash_attr_name = 'subtree_hash'

    """ List of attributes used to compare 2 tasks. """
    tasks_match_attrs = ['name', 'dStart', 'dFinish', 'dAcStart', 'dAcFinish', subtree_hash_attr_name]

    def __init__(self, schedule_a, schedule_b):
        self.schedule_a = schedule_a
        self.schedule_b = schedule_b

        self.result = self._diff()

    def __unicode__(self):
        return self.result_to_str()

    def __str__(self):
        return unicode(self).encode('utf-8')

    def result_to_str(self, items=None, level=0, parent_report_type=REPORT_NO_CHANGE):
        """ Textual representation of the diff. """
        res = ''

        if items is None:
            items = self.result

        for item in items:

            if isinstance(item, Task):
                task = item
                child_tasks = task.tasks

                # apply parent_report_type only if NOT REPORT_CHANGED
                if parent_report_type is REPORT_CHANGED:
                    report_type = REPORT_NO_CHANGE
                else:
                    report_type = parent_report_type

            else:
                child_tasks = item['tasks']
                report_type = item['report_type']

                if item['left'] is None or report_type is REPORT_CHANGED:
                    task = item['right']
                else:
                    task = item['left']

            res += '{} {}{}\n'.format(REPORT_PREFIX_MAP[report_type], level * ' ', str(task))

            if child_tasks:
                res += self.result_to_str(child_tasks, level + 2, report_type)

        return res

    def _create_report(self, report_type, left=None, right=None, tasks=[], changed_attrs=[]):
        """
        Returns a dictionary representing a possible change.

            {
                left: Task or None,
                right: Task or None,
                tasks: List of reports from the child Tasks,
                changed_attr: List of changed attributes,
                report_type: Type of change
            }

        """

        if report_type is REPORT_NO_CHANGE and not tasks:
            report = left

        else:
            # No need to keep the whole structure,
            # child tasks will be placed in report['tasks']
            if left is not None:
                left.tasks = []

            if right is not None:
                right.tasks = []

            report = {
                'left': left,
                'right': right,
                'tasks': tasks,
                'changed_attrs': changed_attrs,
                'report_type': report_type,
            }

        return report

    def task_diff(self, task_a, task_b):
        """
        Uses attributes defined in `tasks_match_attrs` to compare 2 tasks and 
        returns a list of atts that don't match.
        """
        return [attr for attr in self.tasks_match_attrs if getattr(task_a, attr) != getattr(task_b, attr)]

    def find_best_match_index(self, task, in_tasks, start_at_index=0):
        """
        Finds the best match for the given `task` in the `in_tasks` and
        returns the index for the best match and a list of the different attributes.
        """
        match_index = None
        unmatched_attrs = self.tasks_match_attrs[:]

        for i in range(start_at_index, len(in_tasks)):
            unmatched = self.task_diff(task, in_tasks[i])

            # NOTE: maybe 'name' should weight more than the other attrs
            if len(unmatched) < len(unmatched_attrs):
                match_index = i
                unmatched_attrs = unmatched

        return match_index, unmatched_attrs

    def _diff(self, tasks_a=None, tasks_b=None):

        if tasks_a is None:
            tasks_a = self.schedule_a.tasks

        if tasks_b is None:
            tasks_b = self.schedule_b.tasks

        res = []
        last_b_index = 0

        # shortcut to create a report for an added task
        def report_task_added(index):
            task = tasks_b[index]
            return self._create_report(REPORT_ADDED, right=task, tasks=task.tasks)

        for i, task in enumerate(tasks_a):
            match_index, diff_attrs = self.find_best_match_index(task, tasks_b, start_at_index=last_b_index)
            report = {}

            if match_index is None:
                report = self._create_report(REPORT_REMOVED, left=tasks_a[i], tasks=tasks_a[i].tasks)

            else:
                # ALL elements between last_b_index and match_index => ADDED
                res.extend([report_task_added(k) for k in range(last_b_index, match_index)])

                # exact match => NO CHANGE
                if len(diff_attrs) == 0:
                    report = self._create_report(REPORT_NO_CHANGE,
                                                 left=task,
                                                 right=tasks_b[match_index])

                # structural change => CHANGED / NO CHANGE
                elif self.subtree_hash_attr_name in diff_attrs:
                    # process child tasks
                    tasks = self._diff(tasks_a[i].tasks, tasks_b[match_index].tasks)

                    report_type = REPORT_CHANGED if len(diff_attrs) > 1 else REPORT_NO_CHANGE
                    report = self._create_report(report_type,
                                                 left=task,
                                                 right=tasks_b[match_index],
                                                 changed_attrs=diff_attrs,
                                                 tasks=tasks)

                # no structural changes => CHANGED
                else:
                    report = self._create_report(REPORT_CHANGED,
                                                 left=task,
                                                 right=tasks_b[match_index],
                                                 changed_attrs=diff_attrs,
                                                 tasks=tasks_b[match_index].tasks)

                last_b_index = match_index + 1

            res.append(report)

        # remaining tasks => ADDED
        res.extend([report_task_added(k) for k in range(last_b_index, len(tasks_b))])

        return res

    def dump_json(self, **kwargs):

        def _encoder(obj):
            if isinstance(obj, Task):
                return obj.dump_as_dict()
            return jsondate._datetime_encoder(obj)

        kwargs['default'] = _encoder
        return json.dumps(self.result, **kwargs)
