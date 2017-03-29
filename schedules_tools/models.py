import itertools
import pprint
import datetime
import re
import logging
import copy

logger = logging.getLogger(__name__)


class Task(object):
    index = ''
    tjx_id = ''
    name = ''
    note = ''
    priority = 500
    dStart = datetime.datetime.max
    dFinish = datetime.datetime.min
    dAcStart = datetime.datetime.max
    dAcFinish = datetime.datetime.min
    milestone = False
    p_complete = 0
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
        self.level = level

    def __unicode__(self):
        return '%s %s MS:%s  (%s - %s) ac(%s - %s)  F%s  [%s]' % (
            self.tjx_id, self.name, self.milestone, self.dStart, self.dFinish,
            self.dAcStart, self.dAcFinish, self.flags, len(self.tasks))

    def __str__(self):
        return unicode(self).encode('utf-8')

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

    def check_for_phase(self):
        PHASE_NAMES = ('planning phase', 'development phase', 'testing phase',
                       'launch phase', 'maintenance phase')
        if self.name.lower() in PHASE_NAMES:
            self.name = self.name.title()
            self._schedule.phases.append(self)

    @property
    def desc_tasks_count(self):
        count = len(self.tasks)
        for task in self.tasks:
            count += task.desc_tasks_count
        return count

    def get_type(self, check_same_start_finish=False):
        if self.tasks:
            return 'Container'
        elif self.milestone and (not check_same_start_finish or self.dAcStart == self.dAcFinish):
            return 'Milestone'
        else:
            return 'Task'

    def dump_as_dict(self, recursive=True):
        attrs = copy.copy(vars(self))
        exclude = ['_schedule']

        if recursive:
            attrs['tasks'] = []
            for task in self.tasks:
                attrs['tasks'].append(task.dump_as_dict())
        else:
            exclude.append('tasks')

        [attrs.pop(item) for item in exclude]

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


class Schedule(object):
    tj_id = ''
    proj_id = ''
    name = ''  # Product 1.2
    project_name = ''  # Product
    tasks = []
    dStart = None
    dFinish = None
    changelog = {}
    mtime = None

    phases = []
    resources = {}
    assignments = []
    used_flags = None
    ext_attr = {}
    flags_attr_id = None
    id_reg = set()

    _version = {'major': '',
                'minor': '',
                'maint': ''}

    _eTask_list = []
    _task_index = 1

    def __init__(self):
        self.tasks = []
        self.phases = []
        self.used_flags = set()
        self.changelog = {}
        self.ext_attr = {}
        self.unique_task_id_re = re.compile('[\W_]+')

    def override_version(self, tj_id='', v_major='', v_minor='', v_maint=''):
        if tj_id:
            self.proj_id = self.tj_id = tj_id
        if v_major and v_minor and v_maint:
            self._version = {'major': v_major.strip(),
                             'minor': v_minor.strip(),
                             'maint': v_maint.strip()}
        if self.version:
            self.proj_id += self.version.replace('.', '')

    @property
    def version(self):
        out = []
        # order is important
        for ver in [self._version['major'],
                    self._version['minor'],
                    self._version['maint']]:
            if ver != '':
                out.append(ver.replace('-', ''))
        return '.'.join(out).strip(' .')

    def check_top_task(self):
        def _raise_index(task):
            task.index = int(task.index) + 1
            for t in task.tasks:
                _raise_index(t)

        if len(self.tasks) <= 1:
            return

        # need one top task
        top_task = Task(self)
        top_task.index = 1
        #top_task.name = '%s %s' % (self.name, self.version)
        # removed version as per BZ#1396303 - see how that works
        top_task.name = self.name

        for task in self.tasks:
            if top_task.dStart:
                top_task.dStart = min(top_task.dStart,
                                      task.dStart,
                                      task.dAcStart)
            else:
                top_task.dStart = task.dStart

            top_task.dAcStart = top_task.dStart

            if top_task.dFinish:
                top_task.dFinish = max(top_task.dFinish,
                                       task.dAcFinish,
                                       task.dFinish)
            else:
                top_task.dFinish = task.dFinish

            top_task.dAcFinish = top_task.dFinish

            _raise_index(task)
            top_task.tasks.append(task)

        self.tasks = [top_task]

    def print_tasks(self, tasks=None, level=0):
        if tasks is None:
            tasks = self.tasks
        for task in tasks:
            print level * '  ', str(task)
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
        default_attrs = ['name', 'dStart', 'dFinish', 'dAcStart', 'dAcFinish',
                         'link', 'note']
        if not attrs:
            attrs = default_attrs
        ret = ''
        missing_str = ('{}: Some phase upwards is missing to compare with '
                       'this one on the {} side.\n')

        for left, right in itertools.izip_longest(left, right):
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
        attrs = ['name', 'changelog', 'dStart', 'dFinish', 'assignments',
                 'version', 'used_flags']
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

    def get_unique_task_id(self, task, id_prefix):
        # shortcut - first task gets proj id
        if not self.id_reg and id_prefix:
            self.id_reg.add(id_prefix)
            return id_prefix

        pref = copy.copy(id_prefix)
        pref += '.'

        source = self.unique_task_id_re.sub('_', task.name.lower())

        found = False
        test_id = ''
        for word in source.split('_'):
            test_id = pref + word
            if test_id in self.id_reg:
                pref = test_id + '_'
            else:
                found = True
                self.id_reg.add(test_id)
                break

        if not found:
            # duplicate task names - add numbering
            n = 2
            while '%s_%s' % (test_id, n) in self.id_reg:
                n += 1

            test_id = '%s_%s' % (test_id, n)
            self.id_reg.add(test_id)

            logger.info('Duplicate Task Names: %s, adding: %s' % (source, test_id))

        return test_id

    def dump_as_dict(self):
        schedule = copy.copy(vars(self))
        exclude = ['unique_task_id_re']
        [schedule.pop(item) for item in exclude]

        schedule['tasks'] = []
        for task in self.tasks:
            schedule['tasks'].append(task.dump_as_dict())

        schedule['phases'] = []
        for phase in self.phases:
            schedule['phases'].append(phase.dump_as_dict(recursive=False))

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

        schedule.phases = []
        for phase in input_dict['phases']:
            schedule.phases.append(Task.load_from_dict(phase, schedule))

        schedule.used_flags = set(input_dict['used_flags'])

        return schedule
