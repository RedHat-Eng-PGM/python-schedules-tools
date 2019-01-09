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


NAME_SIM_THRESHOLD = 0.8
TASK_SCORE_THRESHOLD = 0.45
NAME_SIM_WEIGHT = 0.5
TASK_POS_WEIGHT = 0.5


"""
Find the Jaro-Winkler distance of 2 strings.
https://en.wikipedia.org/wiki/Jaro-Winkler_distance

:param winkler: add winkler adjustment to the Jaro distance
:param scaling: constant scaling factor for how much the score is adjusted
                upwards for having common prefixes. Should not exceed 0.25
"""
def strings_similarity(str1, str2, winkler=True, scaling=0.1):
    if str1 == str2:
        return 1.0

    def num_of_char_matches(s1, len1, s2, len2):
        count = 0
        transpositions = 0 # number of matching chars w/ different sequence order
        limit = max(len1, len2) / 2 - 1

        for i in range(len1):
            start = i - limit
            if start < 0:
                start = 0

            end = i + limit + 1
            if end > len2:
                end = len2

            index = s2.find(s1[i], start, end)

            if index > -1: # found common char
                count += 1

                if index != i:
                    transpositions += 1

        return count, transpositions

    len1 = len(str1)
    len2 = len(str2)

    num_of_matches, transpositions = num_of_char_matches(str1, len1, str2, len2)

    if num_of_matches == 0:
        return 0.0

    m = float(num_of_matches)
    t = transpositions / 2.0

    dj = (m/float(len1) + m/float(len2) + (m-t)/m) / 3.0

    if winkler:
        l = 0
        # length of common prefix at the start of the string (max = 4)
        max_length = min(
            len1,
            len2,
            4
        )
        while l < max_length and str1[l] == str2[l]:
            l += 1

        return dj + (l * scaling * (1.0 - dj))

    return dj


class ScheduleDiff(object):

    result = []

    hierarchy_attr = 'tasks'
    subtree_hash_attr_name = 'subtree_hash'

    """ List of attributes used to compare 2 tasks. """
    tasks_match_attrs = ['name', 'dStart', 'dFinish', subtree_hash_attr_name]

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
            kwargs = {
                'subtree': self._set_subtree_items_state(self._get_subtree(item), state)
            }

            if state == REPORT_NO_CHANGE:
                kwargs['both'] = item

            elif state == REPORT_ADDED:
                kwargs['right'] = item

            elif state == REPORT_REMOVED:
                kwargs['left'] = item

            return self._create_report(state, **kwargs)

        return [create_report(item) for item in items]

    def get_changed_attrs(self, task_a, task_b):
        """
        Uses attributes defined in `tasks_match_attrs` to compare 2 tasks and
        returns a list of atts that don't match.
        """
        return [attr for attr in self.tasks_match_attrs if getattr(task_a, attr) != getattr(task_b, attr)]

    def find_best_match(self, t1, possible_matches, start_at_index=0):
        """
        Finds the best match for the given task in the list of possible matches.
        Returns the index of the best match and a dict with a state suggestion and list of changed attrs.
        """
        match_index = None
        best_match = {
            'state': REPORT_REMOVED,
            'changes': [],
            'name_score': 0,
            'score': TASK_SCORE_THRESHOLD
        }

        if start_at_index > 0:
            possible_matches = possible_matches[start_at_index:]

        for i, t2 in enumerate(possible_matches, start_at_index):
            res = self.eval_tasks(t1, t2, i, name_threshold=best_match['name_score'])

            if (res['state'] is REPORT_CHANGED
                and res['score'] > best_match['score']):

                match_index = i
                best_match = res

            if res['state'] is REPORT_NO_CHANGE:
                match_index = i
                best_match = res
                break

        return match_index, best_match

    def _task_position_score(self, index):
        return 1.0 / (2 * (index + 1))

    def _task_score(self, name_score, position_score):
        weight_sum = NAME_SIM_WEIGHT + TASK_POS_WEIGHT
        name_score *= NAME_SIM_WEIGHT
        position_score *= TASK_POS_WEIGHT

        return (name_score + position_score) / weight_sum

    def eval_tasks(self, t1, t2, t2_index, name_threshold=NAME_SIM_THRESHOLD):
        name_score = 0.0
        position_score = 0.0
        changed_attrs = self.get_changed_attrs(t1, t2)

        # different names
        if 'name' in changed_attrs:
            t1_subtree = getattr(t1, self.subtree_hash_attr_name)
            t2_subtree = getattr(t2, self.subtree_hash_attr_name)

            if t1_subtree and t2_subtree:
                if t1_subtree == t2_subtree:
                    state = REPORT_CHANGED
                    position_score = 1.0

                else:
                    name_score = strings_similarity(t1.name, t2.name)

                    if (name_score > name_threshold
                        and len(changed_attrs) < len(self.tasks_match_attrs)):
                        state = REPORT_CHANGED
                        position_score = self._task_position_score(t2_index)
                    else:
                        state = REPORT_REMOVED

            # no subtrees
            else:
                name_score = strings_similarity(t1.name, t2.name, winkler=False)

                if name_score > name_threshold:
                    state = REPORT_CHANGED
                    position_score = self._task_position_score(t2_index)
                else:
                    state = REPORT_REMOVED

        # names are equal
        else:
            name_score = 1.0

            if (not changed_attrs
                or (len(changed_attrs) == 1
                and self.subtree_hash_attr_name in changed_attrs)):

                state = REPORT_NO_CHANGE
            else:
                state = REPORT_CHANGED
                position_score = 1.0

        return {
            'state': state,
            'changes': changed_attrs,
            'name_score': name_score,
            'position_score': position_score,
            'score': self._task_score(name_score, position_score)
        }

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

        for task in tasks_a:
            match_index, match = self.find_best_match(task, tasks_b, start_at_index=last_b_index)
            report = {}

            if match_index is None:
                subtree = self._set_subtree_items_state(self._get_subtree(task), REPORT_REMOVED)
                report = self._create_report(REPORT_REMOVED, left=task, subtree=subtree)

            else:
                # ALL elements between last_b_index and match_index => ADDED
                res.extend([report_task_added(k) for k in range(last_b_index, match_index)])

                # exact match => NO CHANGE
                if not match['changes']:
                    subtree = self._set_subtree_items_state(self._get_subtree(task), match['state'])
                    report_kwargs = { 'both': task, 'subtree': subtree }

                # structural change => CHANGED / NO CHANGE
                elif self.subtree_hash_attr_name in match['changes']:

                    # process child tasks
                    subtree = self._diff(
                        self._get_subtree(task),
                        self._get_subtree(tasks_b[match_index])
                    )

                    if len(match['changes']) > 1:
                        report_kwargs = {
                            'left': task,
                            'right': tasks_b[match_index],
                            'subtree': subtree
                        }

                    else:
                        report_kwargs = {
                            'both': task,
                            'subtree': subtree
                        }

                # no structural changes => CHANGED
                else:
                    subtree = self._set_subtree_items_state(
                        self._get_subtree(tasks_b[match_index]), REPORT_NO_CHANGE)

                    report_kwargs = {
                        'left': task,
                        'right': tasks_b[match_index],
                        'subtree': subtree
                    }

                report = self._create_report(match['state'], changed_attrs=match['changes'], **report_kwargs)

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
