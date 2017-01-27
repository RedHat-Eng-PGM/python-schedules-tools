from . import ScheduleHandlerBase
import logging

logger = logging.getLogger('pp.core')
date_format = '%Y-%m-%d'
KNOWN_FLAGS = set([
    'team',

    'partner',
    'partner_hp',

    'interface',

    'roadmap',

    'hidden',

    'qe',
    'marketing',
    'pm',
    'security',
    'devel',
    'docs',
    'releng',
    'support',
    'training',
    'qertt',
    'it',
    'i18n',
    'certification',
    'prod',
    'sysops'
])


class ScheduleHandler_tji(ScheduleHandlerBase):
    provide_export = True

    @staticmethod
    def is_valid_source(handle):
        return False

    # Schedule
    def export_schedule(self, out_file):
        out = ''
        self.schedule.id_reg = set()

        # export unknown flags
        unknown_flags = self.schedule.used_flags - KNOWN_FLAGS
        for flag in unknown_flags:
            out += 'flags %s\n' % flag

        # export tasks
        for item in self.schedule.tasks:
            out += self.task_export_tji(item,
                                        self.schedule.proj_id,
                                        self.schedule.proj_id)

        fp = open(out_file, 'wb')
        fp.write(out.strip().encode('UTF-8'))

    # Task
    def task_export_tji(self, task, id_prefix, proj_id, indent=0):
        return '\n'.join(self.task_prepare_tji(task, id_prefix,
                                               proj_id, indent))

    # Task
    def task_prepare_tji(self, task, id_prefix, proj_id, indent=0):
        """ Returns list of lines """

        ind_ch = '  '
        ind = indent * ind_ch
        d_ind = ind + ind_ch

        task_tji = []
        tj_id = task.tjx_id
        if not tj_id:
            tj_id = self.schedule.get_unique_task_id(task, id_prefix)

        # need to escape double quotes in strings by \\"
        # even backslash needd to be escaped in order to print
        task_tji.append('\n' + ind + 'task %s "%s" {' % (
            tj_id, task.name.replace('"', '\\"')))
        if task.note:
            task_tji.append(d_ind + 'note "%s"' % (
                task.note.replace('"', '\\"')))

        task_tji.append(d_ind + 'start %s' % (
            task.dStart.strftime(date_format)))
        if task.dStart != task.dAcStart:
            task_tji.append(d_ind + 'actual:start %s' % (
                task.dAcStart.strftime(date_format)))
        task_tji.append(d_ind + 'end %s' % (task.dFinish.strftime(date_format)))

        if task.dFinish != task.dAcFinish:
            task_tji.append(d_ind + 'actual:end %s' % (
                task.dAcFinish.strftime(date_format)))

        if task.get_type(check_same_start_finish=True) == 'Milestone':
            task_tji.append(d_ind + 'milestone')

        if task.flags:
            task_tji.append(d_ind + 'flags ' + ', '.join(task.flags))

        if task.link:
            task_tji.append(d_ind + 'PTask ' + task.link)

        if task.tasks:
            for subtask in task.tasks:
                task_tji += self.task_prepare_tji(subtask, tj_id,
                                                  proj_id, indent + 1)

        task_tji.append(ind + '}')

        return task_tji
