import logging

logger = logging.getLogger(__name__)


REPORT_NO_CHANGE = ''
REPORT_ADDED = '_added_'
REPORT_REMOVED = '_removed_'
REPORT_CHANGED = '_changed_'
REPORT_NEW_VALUE = 'new_value'
REPORT_OLD_VALUE = 'old_value'

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

    subtree_hash_attr_name = '_subtree_hash_'

    """ List of attributes used to create the subtree hash. """
    subtree_hash_attrs = ['name', 'dStart', 'dFinish', 'dAcStart', 'dAcFinish']

    """ List of attributes used to compare 2 tasks. """
    tasks_match_attrs = subtree_hash_attrs + [subtree_hash_attr_name]

    def __init__(self, schedule_a, schedule_b):
        self.schedule_a = schedule_a
        self.schedule_b = schedule_b

        self.diff_res = self.diff()

    def _get_or_create_subtree_hash(self, task):
        if self.subtree_hash_attr_name not in task:
            subtree_hash = ''

            for child_task in task['tasks']:
                subtree_hash += ''.join([child_task[attr] for attr in self.subtree_hash_attrs])
                subtree_hash += self._get_or_create_subtree_hash(child_task)

            task[self.subtree_hash_attr_name] = subtree_hash
        return task[self.subtree_hash_attr_name]

    def _create_report(self, report_key, new_value=None, old_value=None):
        """
        Returns a dictionary with the change report.

        @param report_key: one of the REPORT_KEYS elements.
        """
        value = {}

        if report_key == REPORT_CHANGED:
            if new_value is None:
                value[REPORT_NEW_VALUE] = new_value
            if old_value is None:
                value[REPORT_OLD_VALUE] = old_value

        else:  # added or removed
            value = new_value if report_key == REPORT_ADDED else old_value

        return {report_key: value}

    def task_diff(self, task_a, task_b):
        """
        Uses attributes defined in `tasks_match_attrs` to compare 2 tasks and 
        returns a list of atts that don't match.

        It also makes sure that tasks have a `subtree_hash` generated.
        """

        self._get_or_create_subtree_hash(task_a)
        self._get_or_create_subtree_hash(task_b)

        return [attr for attr in self.tasks_match_attrs if a[attr] != b[attr]]

    def find_best_match_index(self, task, in_tasks, start_at_index=0):
        """
        Finds the best match for the given `task` in the `in_tasks` and
        returns the index for the best match and a list of the different attributes.
        """
        match_index = None
        unmatched_attrs = self.tasks_match_attrs[:]

        for i in range(start_at_index, len(in_tasks) - 1):
            unmatched = self.task_diff(task, in_tasks[i])

            if len(unmatched) < len(unmatched_attrs):
                match_index = i
                unmatched_attrs = unmatched

        return match_index, unmatched_attrs

    # WIP
    def diff(self, tasks_a=None, tasks_b=None):

        if tasks_a is None:
            tasks_a = self.schedule_a.tasks

        if tasks_b is None:
            tasks_b = self.schedule_b.tasks

        res = []
        last_b_index = 0
        for i, task in enumerate(tasks_a):
            match_index, diff_attrs = self.find_best_match_index(task, tasks_b, start_at_index=last_b_index)

            if match_index is None:
                # no match => REMOVED
                report = self._create_report(REPORT_REMOVED, old_value=task)
                res.append(report)

            else:
                # TODO:
                #   ALL elements between last_b_index and match_index => ADDED

                last_b_index = match_index

                if len(diff_attrs) == 0:
                    # exact match => NO CHANGE, copy task
                    res.append(task)

                elif self.subtree_hash_attr_name in diff_attrs:
                    # structure changed => NO CHANGE, recursive call on children
                    self.diff(task['tasks'], tasks_b[last_b_index]['tasks'])
                else:
                    # structure NOT changed => CHANGED, no further processing - copy task

        if last_b_index < len(tasks_b) - 1:
            # the rest => ADDED

        return res
