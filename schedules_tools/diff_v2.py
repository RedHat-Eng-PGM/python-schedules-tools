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

    result = None

    subtree_hash_attr_name = 'subtree_hash'

    """ List of attributes used to compare 2 tasks. """
    tasks_match_attrs = ['name', 'dStart', 'dFinish', 'dAcStart', 'dAcFinish', subtree_hash_attr_name]

    def __init__(self, schedule_a, schedule_b):
        self.schedule_a = schedule_a
        self.schedule_b = schedule_b

        self.result = self._diff()

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
        return {
            'left': left,
            'right': right,
            'tasks': tasks,
            'changed_attrs': changed_attrs,
            'report_type': report_type,
        }

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

        for i, task in enumerate(tasks_a):
            match_index, diff_attrs = self.find_best_match_index(task, tasks_b, start_at_index=last_b_index)
            report = {}

            if match_index is None:
                report = self._create_report(REPORT_REMOVED, left=tasks_a[i], tasks=tasks_a[i].tasks)

            else:

                # ALL elements between last_b_index and match_index => ADDED
                for k in range(last_b_index, match_index):
                    report = self._create_report(REPORT_ADDED, right=tasks_b[k], tasks=tasks_b[k].tasks)
                    res.append(report)

                # exact match => NO CHANGE
                if len(diff_attrs) == 0:
                    report = self._create_report(REPORT_NO_CHANGE,
                                                 left=tasks_a[i],
                                                 right=tasks_b[match_index],
                                                 tasks=tasks_b[match_index].tasks)

                # structural change => CHANGED / NO CHANGE
                elif self.subtree_hash_attr_name in diff_attrs:

                    # process child tasks
                    tasks = self._diff(tasks_a[i].tasks, tasks_b[match_index].tasks)

                    report_type = REPORT_CHANGED if len(diff_attrs) > 1 else REPORT_NO_CHANGE
                    report = self._create_report(report_type,
                                                 left=tasks_a[i],
                                                 right=tasks_b[match_index],
                                                 changed_attrs=diff_attrs,
                                                 tasks=tasks)

                # no structural changes => CHANGED
                else:
                    report = self._create_report(REPORT_CHANGED,
                                                 left=tasks_a[i],
                                                 right=tasks_b[match_index],
                                                 changed_attrs=diff_attrs,
                                                 tasks=tasks_b[match_index].tasks)

                last_b_index = match_index

            res.append(report)

        # remaining tasks => ADDED
        for k in range(last_b_index + 1, len(tasks_b)):
            report = self._create_report(REPORT_ADDED, right=tasks_b[k], tasks=tasks_b[k].tasks)
            res.append(report)

        return res

    def dump_json(self, **kwargs):

        def _encoder(obj):
            if isinstance(obj, Task):
                return obj.dump_as_dict(recursive=False)
            return jsondate._datetime_encoder(obj)

        kwargs['default'] = _encoder
        return json.dumps(self.result, **kwargs)
