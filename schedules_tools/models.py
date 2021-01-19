import pprint
import datetime
import re
import logging

from copy import copy

from itertools import zip_longest

from schedules_tools import SchedulesToolsException

from .utils import sort_tasks, slugify

log = logging.getLogger(__name__)
re_flags_separator = re.compile(r'[, ]+')

ATTR_PREFIX_FLAG = 'Flags'
ATTR_PREFIX_LINK = 'Link'
ATTR_PREFIX_NOTE = 'Note'

TASK_SLUG_NUMERATION_LIMIT = 9999
TASK_SLUG_CHAR_LIMIT = 255
TASK_SLUG_TRUNCATION_LIMIT = TASK_SLUG_CHAR_LIMIT - (1 + len(str(TASK_SLUG_NUMERATION_LIMIT)))


class Task(object):
    index = ''
    slug = ''
    name = ''
    note = ''
    priority = 500
    dStart = datetime.datetime.max
    dFinish = datetime.datetime.min
    duration = None
    milestone = False
    p_complete = 0.0
    flags = []
    level = 1
    link = ''

    tasks = []

    resource = None

    _date_format = '%Y-%m-%dT%H:%M:%S'
    _rx = None
    _schedule = None

    def __init__(self, schedule=None, level=1):
        self.tasks = []
        self.flags = []
        self._schedule = schedule
        self.p_complete = 0.0
        self.priority = 500
        self.milestone = False
        self.level = level
        self._subtree_hash_cache = {}

    def __str__(self):
        return f'{self.slug} {self.name} MS:{self.milestone}  ({self.dStart} - {self.dFinish})  ' \
               f'F{self.flags}  [{len(self.tasks)}]'

    def parse_extended_attr(self, value, key=None):
        """
        According to given value it will guess if it is flag, link or note
        definition and fill proper task attribute.

        Args:
            value: string to parse, or set attribute specified by 'key' arg
            key: (optional) set value to task attribute according to this key
        """
        if not value:
            return

        if key:
            val = value
        elif hasattr(value, 'split'):
            # test value for flag / note / link
            pieces = value.split(':', 1)
            if len(pieces) != 2:
                # it's not a string in format 'Flag: qe, dev' - don't process
                return

            key, val = pieces
            key = key.strip().lower()
            val = val.strip()

        else:
            return

        if key.lower() == ATTR_PREFIX_FLAG.lower():
            val = str(val).lower()
            flags = re_flags_separator.split(val)
            for flag in flags:
                flag = str(flag.strip())
                if flag:
                    self.flags.append(flag)
            self._schedule.used_flags |= set(self.flags)

        elif key.lower() == ATTR_PREFIX_LINK.lower():
            self.link = str(val)

        elif key.lower() == ATTR_PREFIX_NOTE.lower():
            # in case of multiple notes - concatenate
            self.note = ' '.join([self.note, val]).lstrip()

        else:
            log.info(f'Extended attr "{key}" wasn\'t recognized.')

    @staticmethod
    def _workaround_it_phase_names(eTask):
        """Corrects phase names"""
        name_map = {'Concept': 'Concept Phase',
                    'Planning': 'Planning Phase',
                    'Develop': 'Development Phase',
                    'Test': 'Testing Phase',
                    'Launch': 'Launch Phase',
                    'Maintenance': 'Maintenance Phase',
                    }

        eName_list = eTask.xpath('Name')
        if eName_list:
            name = eName_list[0].text
            if name:
                name = name.strip()

            level = int(eTask.xpath('OutlineLevel')[0].text)

            if level in [1, 2] and name in name_map.keys():
                # check that there is no full named task else in the schedule
                root = eTask.getroottree()
                eFullnamed_task_list = root.xpath('//Task[Name = "%s"]' % name_map[name])

                if not eFullnamed_task_list:  # if not - map the name
                    return name_map[name]
            return name
        return ''

    @property
    def desc_tasks_count(self):
        count = len(self.tasks)
        for task in self.tasks:
            count += task.desc_tasks_count
        return count

    def get_type(self, check_same_start_finish=False):
        if self.tasks:
            return 'Container'
        elif self.milestone and (not check_same_start_finish or self.dStart == self.dFinish):
            return 'Milestone'
        else:
            return 'Task'

    def dump_as_dict(self, recursive=True):
        attrs = copy(vars(self))
        # avoid infinite looping schedule > task > schedule ...
        exclude = ['_schedule', '_subtree_hash_cache']

        if recursive:
            attrs['tasks'] = []
            for task in self.tasks:
                attrs['tasks'].append(task.dump_as_dict())
        else:
            exclude.append('tasks')

        [attrs.pop(item) for item in exclude if item in attrs]

        return attrs

    @classmethod
    def load_from_dict(cls, input_dict, schedule):
        task = cls(schedule)

        for key, val in input_dict.items():
            task.__setattr__(key, val)

        task.tasks = []
        for new_task in input_dict.get('tasks', []):
            task.tasks.append(Task.load_from_dict(new_task, schedule))

        return task

    def get_subtree_hash(self, fields):
        if not isinstance(fields, tuple):
            fields = tuple(fields)

        if fields not in self._subtree_hash_cache:
            if self.tasks:
                hashes = []
                for child_task in self.tasks:
                    task_hash_values = []
                    for attr_name in fields:
                        attr_value = getattr(child_task, attr_name)

                        if isinstance(attr_value, list):
                            attr_value = sorted(attr_value)

                        task_hash_values.append(str(attr_value))

                    hashes.append(
                        '%s%s' % (
                            ''.join(task_hash_values),
                            child_task.get_subtree_hash(fields)
                        )
                    )

                subtree_hash = ''.join(hashes)

            else:
                subtree_hash = ''

            self._subtree_hash_cache[fields] = subtree_hash

        return self._subtree_hash_cache[fields]

    def get_slug_key(self, prefix=None):
        """
        Generates slug key only for the task itself.
        Doesn't include parent tasks slugs i.e. slug key is not a full slug path to the task.
        """
        slug_key = slugify(self.name)

        if prefix is not None:
            return '.'.join((prefix, slug_key))
        return slug_key


class Schedule(object):
    slug = ''
    name = ''  # Product 1.2
    tasks = []
    dStart = None
    dFinish = None
    changelog = {}
    mtime = None

    resources = {}
    assignments = []
    used_flags = None
    ext_attr = {}
    flags_attr_id = None
    id_reg = set()

    _eTask_list = []
    _task_index = 1
    _taskname_flat_registry = None

    errors_import = []

    def __init__(self):
        self.tasks = []
        self.used_flags = set()
        self.changelog = {}
        self.ext_attr = {}
        self.unique_id_re = re.compile(r'[\W_]+')
        self.errors_import = []
        self.mtime = None
        self.tasks_slugs = None

    def make_flat(self):
        '''Convert tasks structure to flat list'''
        def add_tasks_to_list(tasks, tasks_list):
            for task in tasks:
                subtasks = copy(task.tasks)
                task.tasks = []
                tasks_list.append(task)
                add_tasks_to_list(subtasks, tasks_list)

        flat_tasks = []
        add_tasks_to_list(self.tasks, flat_tasks)
        self.tasks = flat_tasks

    def filter_milestones(self):
        '''Keep only tasks that are milestones or contain children that are'''
        def filter_tasks(tasks):
            tasks_list = []
            for task in tasks:
                filtered_subtasks = filter_tasks(task.tasks)

                logmsg_fmt = 'REMOVE: {} {}'

                if task.milestone or filtered_subtasks:
                    task.tasks = filtered_subtasks
                    tasks_list.append(task)
                    logmsg_fmt = 'ADD: {} {}'

                log.info(logmsg_fmt.format(task.name, task.milestone))

            return tasks_list

        self.tasks = filter_tasks(self.tasks)

    def filter_flags(self, show=None, hide=None):
        '''
        Keep only tasks that match flag conditions or contain children tha match

        Args:
            show: list of flags to show
            hide: list of flags to hide
        '''

        def filter_tasks(tasks):
            tasks_list = []
            for task in tasks:
                # see if there are any matching children
                filtered_subtasks = filter_tasks(task.tasks)

                # Add to result if not hidden and (has subtasks or fits show)
                logmsg_fmt = 'REMOVE: {} {}'
                if (not (set(task.flags) & set(hide))
                    and (filtered_subtasks
                         or (set(task.flags) & set(show))
                         or not show)):
                    task.tasks = filtered_subtasks
                    tasks_list.append(task)

                    logmsg_fmt = 'ADD: {} {}'

                    self.used_flags.update(task.flags)

                log.info(logmsg_fmt.format(task.name, task.flags))

            return tasks_list

        if show is None:
            show = []
        if hide is None:
            hide = []

        if show or hide:
            self.used_flags = set()

            log.info('FLAG filter: SHOW {}   HIDE {}'.format(show, hide))

            self.tasks = filter_tasks(self.tasks)

    def sort_tasks(self, field):
        self.tasks = sort_tasks(self.tasks, field)

    def check_top_task(self):
        """ Add single root task if multiple """

        def _raise_index(task):
            task.index = int(task.index) + 1
            for t in task.tasks:
                _raise_index(t)

        if len(self.tasks) <= 1:
            return

        # need one top task
        top_task = Task(self)
        top_task.index = 1
        # top_task.name = '%s %s' % (self.name, self.version)
        # removed version as per BZ#1396303 - see how that works
        top_task.name = self.name
        top_task.slug = self.slug

        for task in self.tasks:
            if top_task.dStart:
                top_task.dStart = min(top_task.dStart,
                                      task.dStart)
            else:
                top_task.dStart = task.dStart

            if top_task.dFinish:
                top_task.dFinish = max(top_task.dFinish,
                                       task.dFinish)
            else:
                top_task.dFinish = task.dFinish

            _raise_index(task)
            top_task.tasks.append(task)

        self.tasks = [top_task]

    def generate_slugs(self):
        def gen_slugs_recursive(tasks, slug_prefix=None):
            for task in tasks:
                task_slug = task.get_slug_key(slug_prefix)

                if len(task_slug) > TASK_SLUG_TRUNCATION_LIMIT:
                    task_slug = task_slug[:TASK_SLUG_TRUNCATION_LIMIT]

                if task_slug in self.tasks_slugs:
                    for i in range(2, TASK_SLUG_NUMERATION_LIMIT + 1):
                        task_slug_numerated = '%s_%d' % (task_slug, i)
                        if task_slug_numerated not in self.tasks_slugs:
                            final_task_slug = task_slug_numerated
                            break
                        elif i == TASK_SLUG_NUMERATION_LIMIT:
                            raise SchedulesToolsException('Task slug generation error: '
                                                          'reached numeration limit')
                else:
                    final_task_slug = task_slug

                task.slug = final_task_slug
                self.tasks_slugs.add(task.slug)
                gen_slugs_recursive(task.tasks, task.slug)

        self.tasks_slugs = set()
        gen_slugs_recursive(self.tasks)

    def print_tasks(self, tasks=None, level=0):
        if tasks is None:
            tasks = self.tasks
        for task in tasks:
            print(level * '  ', str(task))
            if task.tasks:
                self.print_tasks(task.tasks, level + 1)

    @staticmethod
    def _diff_task_attrs(left, right, attrs, whole_days=False):
        diff = {}

        for a in attrs:
            left_val = left.__getattribute__(a)
            right_val = right.__getattribute__(a)
            if left_val != right_val:
                try:
                    if whole_days and \
                                    left_val.day == right_val.day and \
                                    left_val.month == right_val.month and \
                                    left_val.year == right_val.year:
                        # When we compare just whole days, we don't mind
                        # to have diff in time
                        continue
                except AttributeError:
                    pass

                diff[a] = (str(left_val), str(right_val))
        return diff

    def _diff_tasks(self, left, right, attrs=None, whole_days=False):
        default_attrs = ['name', 'dStart', 'dFinish', 'link', 'note']
        if not attrs:
            attrs = default_attrs
        ret = ''
        missing_str = ('{}: Some phase upwards is missing to compare with '
                       'this one on the {} side.\n')

        for left, right in zip_longest(left, right):
            if not left:
                ret += missing_str.format(right.name, 'LEFT')
                break
            if not right:
                ret += missing_str.format(left.name, 'RIGHT')
                break

            d = self._diff_task_attrs(left, right, attrs, whole_days)
            if len(d):
                name_warning = ''
                if 'name' in d.keys():
                    name_warning = (' <--- Name of the phase doesn\'t match. '
                                    'Missing phase?')
                # width=1 force wrap tuple to newline
                ret += '{}:{}\n{}\n'.format(
                    left.name,
                    name_warning,
                    pprint.pformat(d, width=1)
                )

            ret += self._diff_tasks(left.tasks, right.tasks, attrs, whole_days)
        return ret

    def _diff_schedule_attrs(self, schedule, whole_days=False):
        attrs = ['name', 'changelog', 'dStart', 'dFinish', 'assignments', 'used_flags']
        ret = ''
        diff = dict()

        for attr in attrs:
            self_s = self.__getattribute__(attr)
            schedule_s = schedule.__getattribute__(attr)

            if self_s != schedule_s:
                try:
                    if whole_days and \
                                    self_s.day == schedule_s.day and \
                                    self_s.month == schedule_s.month and \
                                    self_s.year == schedule_s.year:
                        # When we compare just whole days, we don't mind
                        # to have diff in time
                        continue
                except AttributeError:
                    pass
                diff[attr] = (str(self_s), str(schedule_s))

        if len(diff):
            # width=1 force wrap tuple to newline
            ret += 'Schedule attrs:\n'
            ret += pprint.pformat(diff, width=1)
        return ret

    def _diff_schedule_version(self, schedule):
        attrs = self._version.keys()
        ret = ''
        diff = dict()

        for attr in attrs:
            self_s = self._version[attr]
            schedule_s = self._version[attr]

            if self_s != schedule_s:
                diff[attr] = (self_s, schedule_s)

        if len(diff):
            # width=1 force wrap tuple to newline
            ret += 'Schedule version:\n'
            ret += pprint.pformat(diff, width=1)

        return ret

    def diff(self, schedule, attrs=None, whole_days=False):
        """
        Really simple diff to match two schedules.

        @param schedule Instance to another schedule to figure out differences
        @param attrs Task attributes to check
        @param whole_days Flag to ignore time differences of dates
        """
        ret = ''
        diff_tasks = self._diff_tasks(self.tasks, schedule.tasks, attrs,
                                      whole_days)
        if diff_tasks:
            ret += 'Tasks attrs:\n'
            ret += diff_tasks
        ret += self._diff_schedule_attrs(schedule, whole_days=whole_days)

        return ret.strip()

    def slugify_str(self, orig_str):
        return self.unique_id_re.sub('_', orig_str.lower())

    def dump_as_dict(self):
        schedule = copy(vars(self))

        schedule['tasks'] = []
        for task in self.tasks:
            schedule['tasks'].append(task.dump_as_dict())

        # set() is not serializable into json
        schedule['used_flags'] = sorted(list(self.used_flags))
        return schedule

    @classmethod
    def load_from_dict(cls, input_dict):
        # This will preserve reference to original class attributes
        schedule = cls()
        for key, val in input_dict.items():
            schedule.__setattr__(key, val)

        schedule.tasks = []
        for task in input_dict['tasks']:
            schedule.tasks.append(Task.load_from_dict(task, schedule))

        schedule.used_flags = set(input_dict['used_flags'])

        return schedule

    def _build_tasks_flat_registry(self, tasks_param):
        if self._taskname_flat_registry is None:
            self._taskname_flat_registry = set()

        for task in tasks_param:
            self._taskname_flat_registry.add(task.name)
            self._build_tasks_flat_registry(task.tasks)

    def check_for_taskname(self, tasks):
        """
        Method consume list of task names to check their existence specified
        as dict
        Args:
            tasks: dict specification of task names to check. Example:
            {'exactTaskname': False, 'matchBeginningTaskname': True}

        Returns:
            Set of task names, that haven't been found in schedule.

        """
        if not isinstance(tasks, dict):
            raise Exception(
                "'tasks' argument has to be dict, for example: {'task1': False,"
                " 'matchBeginningTaskname': True}")

        if not self._taskname_flat_registry:
            self._build_tasks_flat_registry(self.tasks)

        missing_tasks = set()
        for task_name, start_with_flag in tasks.items():
            if start_with_flag:
                re_task_str = re.escape(task_name)
                re_task = re.compile(re_task_str + '.*')
                found = False

                for task in self._taskname_flat_registry:
                    if re_task.match(task):
                        found = True
                        break
                if not found:
                    missing_tasks.add(task_name)
            elif task_name not in self._taskname_flat_registry:
                missing_tasks.add(task_name)

        return missing_tasks
