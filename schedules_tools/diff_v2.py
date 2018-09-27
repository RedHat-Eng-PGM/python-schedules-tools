import logging
import json

from schedules_tools import jsondate
from schedules_tools.models import Task

log = logging.getLogger(__name__)


REPORT_NO_CHANGE = ''
REPORT_ADDED = '_added_'
REPORT_REMOVED = '_removed_'
REPORT_CHANGED = '_changed_'

REPORT_PREFIX_MAP = {
    REPORT_ADDED: '[+]',
    REPORT_REMOVED: '[-]',
    REPORT_CHANGED: '[M]',
    REPORT_NO_CHANGE: 3 * ' ',
}


class ScheduleDiff(object):

    result = []

    hierarchy_attr = 'tasks'
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

    def _get_subtree(self, item):
        return getattr(item, self.hierarchy_attr)

    def result_to_str(self, items=None, level=0):
        """ Textual representation of the diff. """
        res = ''

        if items is None:
            items = self.result

        for item in items:
            subtree = item['subtree']
            state = item['item_state']

            if state in [REPORT_CHANGED, REPORT_ADDED]:
                task = item['right']
            elif state is REPORT_REMOVED:
                task = item['left']
            else:
                task = item['both']

            res += '{} {}{}\n'.format(REPORT_PREFIX_MAP[state], level * ' ', str(task))

            if subtree:
                res += self.result_to_str(subtree, level + 2)

        return res

    def _create_report(self,
                       item_state,
                       left=None,
                       right=None,
                       both=None,
                       subtree=[],
                       changed_attrs=[]):
        """
        Returns a dictionary representing a possible change.

            {
                left: Task or None,
                right: Task or None,
                both: used instead of left and right, when the task are equal,
                subtree: List of reports from the child Tasks,
                changed_attr: List of changed attributes,
                item_state: Type of change
            }

        """

        if both:
            report = {
                'both': both.dump_as_dict(recursive=False),
                'subtree': subtree,
                'changed_attrs': changed_attrs,
                'item_state': item_state
            }

        else:
            # No need to keep the whole structure,
            # child tasks will be placed in report['tasks']
            if left is not None:
                left = left.dump_as_dict(recursive=False)

            if right is not None:
                right = right.dump_as_dict(recursive=False)

            report = {
                'left': left,
                'right': right,
                'subtree': subtree,
                'changed_attrs': changed_attrs,
                'item_state': item_state,
            }

        return report

    def _set_subtree_items_state(self, items, state):
        """
        Set the given state recursively on the subtree items
        """

        def create_report(item):
            if state == REPORT_NO_CHANGE:
                kwargs = { 'both': item }

            elif state == REPORT_ADDED:
                kwargs = { 'right': item }

            elif state == REPORT_REMOVED:
                kwargs = { 'left': item }

            kwargs['subtree'] = self._set_subtree_items_state(self._get_subtree(item), state)

            return self._create_report(state, **kwargs)

        return [create_report(item) for item in items]

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
        def report_task_added(index, recursive=True):
            task = tasks_b[index]
            subtree = self._get_subtree(task)

            if recursive:
                subtree = self._set_subtree_items_state(subtree, REPORT_ADDED)

            return self._create_report(REPORT_ADDED, right=task, subtree=subtree)

        for i, task in enumerate(tasks_a):
            match_index, diff_attrs = self.find_best_match_index(task, tasks_b, start_at_index=last_b_index)
            report = {}

            if match_index is None:
                subtree = self._set_subtree_items_state(self._get_subtree(tasks_a[i]), REPORT_REMOVED)
                report = self._create_report(REPORT_REMOVED, left=tasks_a[i], subtree=subtree)

            else:
                # ALL elements between last_b_index and match_index => ADDED
                res.extend([report_task_added(k) for k in range(last_b_index, match_index)])

                # exact match => NO CHANGE
                if len(diff_attrs) == 0:
                    report_type = REPORT_NO_CHANGE
                    subtree = self._set_subtree_items_state(self._get_subtree(task), report_type)
                    report_kwargs = { 'both': task, 'subtree': subtree }

                # structural change => CHANGED / NO CHANGE
                elif self.subtree_hash_attr_name in diff_attrs:

                    # process child tasks
                    subtree = self._diff(
                        self._get_subtree(tasks_a[i]),
                        self._get_subtree(tasks_b[match_index])
                    )

                    if len(diff_attrs) > 1:
                        report_type = REPORT_CHANGED
                        report_kwargs = {
                            'left': task,
                            'right': tasks_b[match_index],
                            'changed_attrs': diff_attrs,
                            'subtree': subtree
                        }

                    else:
                        report_type = REPORT_NO_CHANGE
                        report_kwargs = {
                            'both': task,
                            'changed_attrs': diff_attrs,
                            'subtree': subtree
                        }

                # no structural changes => CHANGED
                else:
                    subtree = self._set_subtree_items_state(
                        self._get_subtree(tasks_b[match_index]), REPORT_NO_CHANGE)

                    report_type = REPORT_CHANGED
                    report_kwargs = {
                        'left': task,
                        'right': tasks_b[match_index],
                        'changed_attrs': diff_attrs,
                        'subtree': subtree
                    }

                report = self._create_report(report_type, **report_kwargs)

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
