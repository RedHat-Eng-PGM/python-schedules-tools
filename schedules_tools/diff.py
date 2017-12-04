import json
import re
import logging

from schedules_tools import jsondate
from deepdiff import DeepDiff
from deepdiff.helper import NotPresent

logger = logging.getLogger(__name__)


def _custom_json_encoder(obj):
    if isinstance(obj, set):
        return list(obj)
    return jsondate._datetime_encoder(obj)


class ScheduleDiff(object):

    def __init__(self, schedule_a, schedule_b):
        self.schedule_a = schedule_a
        self.schedule_b = schedule_b

        self.schedule_a_dict = schedule_a.dump_as_dict()
        self.schedule_b_dict = schedule_b.dump_as_dict()

        self.diff = DeepDiff(self.schedule_a_dict, self.schedule_b_dict,
                             verbose_level=0,  # ignore type changes
                             view='tree'
                             )

    def filter_attrs(self, in_dict, attrs):
        return {k: v for k, v in in_dict.iteritems() if k in attrs}

    def walk_dict(self, in_dict, keys_list):
        """ Returns the value of the given keys_list path in the dictionary. """

        if len(keys_list) > 0:
            key = keys_list.pop(0)

            if isinstance(in_dict, list):
                item = in_dict[int(key)]
            else:
                item = in_dict[key]

            in_dict = self.walk_dict(item, keys_list)
        return in_dict

    def path_to_keys(self, path):
        """
        Transforms a path str into list of keys,
        collecting only the values wrapped with brackets.

        Example: "root['attr1'][1]" becomes ['attr1', '1']
        """
        return re.findall(r"\[[']*([\w.]+)[']*\]", path)

    def _create_change_report(self, change_type, new_value, old_value):
        """
        Returns a dictionary with the change report.

        @param change_type: "added", "removed" or "changed"
        """
        change_value = {}
        change_key = '_%s_' % change_type

        if change_type == 'changed':
            if not isinstance(new_value, NotPresent):
                change_value['new_value'] = new_value
            if not isinstance(old_value, NotPresent):
                change_value['old_value'] = old_value

        else:  # added or removed
            change_value = new_value if change_type == 'added' else old_value

        return {change_key: change_value}

    def _add_change_report(self, to_dict, change):
        """
        Place a change report in the given dictionary, using the path of the change object.

        NOTE:

            Changes with paths not found in the given dictionary will be skipped.

        @param to_dict: dictionary to be updated with the change reports
        @param change: DiffLevel object that represents a change.
        """
        change_type = change.report_type.split('_')[-1]  # added, removed or changed
        path = self.path_to_keys(change.path())
        changed_key = path.pop()

        try:
            parent = self.walk_dict(to_dict, path)
        except (ValueError, KeyError):
            logger.warning("Change skipped."
                           "Could not find any item with the path: %s" % change.path())
            return

        change_report = self._create_change_report(change_type,
                                                   new_value=change.t2,
                                                   old_value=change.t1)

        if isinstance(parent, list):
            parent.insert(int(changed_key), change_report)
        else:
            parent[changed_key] = change_report

    def dump_dict(self, schedule_attrs=[]):
        """
        Returns a dictionary that represents the result of the diff.

        @param  schedule_attrs: Set of schedule attrs to be returned.
                                If not specified, will return all attrs.
        """
        filter_attrs = schedule_attrs or self.schedule_a_dict.keys()
        diff_dict = self.filter_attrs(self.schedule_a_dict, filter_attrs)

        for key, changes in self.diff.iteritems():
            for change in changes:
                path = change.path()
                sched_attr = self.path_to_keys(path)[0]

                if sched_attr in filter_attrs:
                    self._add_change_report(diff_dict, change)

        return diff_dict

    def dump_json(self, schedule_attrs=[], **kwargs):
        """
        Serialize diff result to a JSON formatted str.

        @param  schedule_attrs: Set of schedule attrs to be returned.
                                If not specified, will return all attrs.
        @param  **kwargs: Can be used to pass in arguments to json.dumps().
        """
        kwargs['default'] = _custom_json_encoder
        res_dict = self.dump_dict(schedule_attrs)
        return json.dumps(res_dict, **kwargs)
