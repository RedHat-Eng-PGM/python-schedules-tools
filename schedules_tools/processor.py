#!/usr/bin/env python3

import argparse
from datetime import timedelta
import logging
from multiprocessing import Process, Manager
import os
import re
from rh_pp_api_client import PPApi
from rh_pp_api_client.base import PPApiException
import textwrap

from dateutil import parser


pp_client_log = logging.getLogger('rh_pp_api_client')
log = logging.getLogger(__name__)


def setup_logging(level='ERROR'):
    pp_client_log = logging.getLogger('rh_pp_api_client')
    log = logging.getLogger(__name__)

    h = logging.StreamHandler()
    h.setLevel(getattr(logging, level.upper()))

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    h.setFormatter(formatter)

    pp_client_log.addHandler(h)
    log.addHandler(h)


def chunkify(values, n):
    """Yields n of roughly equal chunks from values"""
    for i in range(n):
        yield values[i::n]


class ScheduleProcessingException(Exception):
    pass


class ScheduleProcessor(object):
    """Replace directives in schedules

    Attributes:
        DATE_REPLACE_REGEXP: Directive expression
        client: Instance of PP API client
        p_workers: Number of parallel workers (default 4)
        look_for: Dictionary of gathered directives
        _task_cache: id mapped dictionary with tasks data
        _multiproc_manager: used to share data among workers
    """

    # {{rhel-7-0|task_id2|ac_date_finish|+4d}}
    DATE_REPLACE_REGEXP = \
        r'\{\{(?P<release>[^|]*)\|(?P<task>[^|]*)\|(?P<date_type>[^|]*)(\|(?P<offset>[^|]*))?\}\}'
    # -12w | +2d | 3d
    OFFSET_REGEXP = r'(?P<number>[+-]?\d+)(?P<period>[wd])'

    client = None  # api_client
    p_workers = 4

    look_for = None

    _tasks_cache = None
    _multiproc_manager = None

    def __init__(self, pp_api_client=None, p_workers=4):
        if pp_api_client is None:
            pp_api_client = PPApi()

        self.client = pp_api_client

        self.p_workers = p_workers

        self._multiproc_manager = Manager()

        self.look_for = {}
        self._tasks_cache = {}

    def gather_directives(self, src):
        """Read source string and build look_for dict"""
        found = False

        for directive in [m.groupdict() for m in re.finditer(self.DATE_REPLACE_REGEXP,
                                                             src)]:
            found = True

            release = directive['release']
            task = directive['task']

            if release not in self.look_for:
                self.look_for[release] = {'ids': {}}
            if task not in self.look_for[release]['ids']:
                self.look_for[release]['ids'][task] = None

        return found

    def load_schedules(self):
        def load_schedules_worker(releases, look_for, cache, worker_id=None):
            for release in releases:
                log.debug('Worker %s: Loading release %s' % (worker_id, release))

                try:
                    rel_id = self.client.releases.get_id(release)
                    src_tasks = self.client.releases.schedules_tasks.list(rel_id)

                    cache_id_map = {}
                    look_for_release = look_for[release]

                    for t in src_tasks:
                        # if looked for - put it into look aside cache
                        if t['tj_id'] in look_for_release['ids']:
                            # update look_for and cache
                            look_for_release['ids'][t['tj_id']] = t['id']
                            cache_id_map[t['id']] = t

                    if release not in cache:
                        cache[release] = cache_id_map

                    look_for[release] = look_for_release

                except PPApiException as e:
                    log.error(e)
                    del look_for[release]  # don't try to replace

        cache = self._multiproc_manager.dict()
        look_for = self._multiproc_manager.dict(self.look_for)

        jobs = []
        # split releases into equal chunks and prepare workers
        for worker_id, rel_chunk in enumerate(chunkify(self.look_for.keys(),
                                                       self.p_workers)):
            process = Process(
                        target=load_schedules_worker,
                        args=(rel_chunk, look_for, cache, worker_id))
            jobs.append(process)

        for j in jobs:
            j.start()

        for j in jobs:
            j.join()

        self._tasks_cache = dict(cache)
        self.look_for = dict(look_for)

    def check_date(self, date, direction=1):
        '''Check that date is not weekend and move

        Args:
          date: date object
          direction: +1 | -1 int saying where to move until not weekend
        '''

        day = timedelta(days=int(direction))

        while date.weekday() > 4:
            date = date + day

        return date

    def replace_directives(self, src, log_src=''):
        def replace_directive(match):
            directive = match.groupdict()

            release = directive['release']
            task = directive['task']
            date_type = directive['date_type']
            offset = directive['offset']

            # we might have removed release because of api errors, ...
            if release in self.look_for:
                log.debug('Replacing %s %s %s' % (release, task, date_type))

                # handle optional offset - +- number days/weeks
                tdelta_offset = None
                if offset:
                    match_offset = re.match(self.OFFSET_REGEXP, offset)

                    if match_offset:
                        offset = match_offset.groupdict()

                        if offset['period'] == 'd':  # days
                            tdelta_offset = timedelta(days=int(offset['number']))
                        elif offset['period'] == 'w':  # weeks
                            tdelta_offset = timedelta(weeks=int(offset['number']))

                        tdelta_direction = 1 if abs(tdelta_offset) == tdelta_offset else -1
                    else:
                        log.error('(%s) Wrong offset format "%s"!' % (log_src, offset))

                task_id = self.look_for[release]['ids'][task]

                if task_id is not None:
                    iso_date = self._tasks_cache[release][task_id][date_type]

                    if tdelta_offset:  # apply offset
                        off_date = parser.parse(iso_date) + tdelta_offset
                        return self.check_date(off_date, tdelta_direction).strftime('%Y-%m-%d')
                    else:
                        return iso_date
                else:
                    log.error('(%s) Task ID "%s" doesn\'t exist in %s schedule!' %
                              (log_src, task, release))

            return match.group()

        out = re.sub(self.DATE_REPLACE_REGEXP, replace_directive, src)
        return out

    def process_schedules(self, schedules, inplace=False):
        """ Replace directives by dates in schedules

            Args:
                schedules: either filename or list of filenames and/or directories
                inplace: replace source files
        """

        filelist = []

        if not type(schedules) in (list, set):
            schedules = [schedules]

        for schedule_src in schedules:
            # determine if it's file or dir
            if os.path.isdir(schedule_src):
                for root, _, files in os.walk(schedule_src):
                    for filename in files:
                        filelist.append(os.path.join(root, filename))
            elif os.path.isfile(schedule_src):
                filelist.append(schedule_src)

        # gather directives one src by one
        for filename in filelist:
            with open(filename, 'r') as f:
                if not self.gather_directives(f.read()):
                    filelist.remove(filename)

        self.load_schedules()  # load schedules in parallel

        # replace in parallel (use file, not src - to split into workers
        def replace_directives_worker(filenames, inplace=False, worker_id=None):
            for filename in filenames:
                log.debug('Worker %s: Processing file %s' % (worker_id, filename))

                if inplace:  # generate out file name
                    filename_out = filename
                else:
                    root, ext = os.path.splitext(filename)
                    filename_out = root + '.out' + ext

                out = ''
                with open(filename, 'r') as f:
                    out = self.replace_directives(f.read(), filename)

                if out:
                    with open(filename_out, 'w') as f:
                        f.write(out)

        jobs = []
        # split files into equal chunks and prepare workers
        for worker_id, files_chunk in enumerate(chunkify(filelist,
                                                         self.p_workers)):
            process = Process(target=replace_directives_worker,
                              args=(files_chunk, inplace, worker_id))
            jobs.append(process)

        for j in jobs:
            j.start()

        for j in jobs:
            j.join()


def main():
    parser = argparse.ArgumentParser(
                formatter_class=argparse.RawDescriptionHelpFormatter,
                description=textwrap.dedent('''
                    Schedule Pre-processor
                    Replaces {{release|task_id|date_type|offset}} directives by real dates.

                    Unless 'inplace' option is set, output files extension will be prefixed by 'out'

                    date_type: date_start|date_finish|ac_date_start|ac_date_finish
                    offset: +4d | -2w | 30d

                    https://docs.engineering.redhat.com/display/EPM/process_schedules

                    '''))
    parser.add_argument('input_list', nargs='+',
                        help='List of files/directories with schedules')
    parser.add_argument('-i', '--inplace', action='store_true', dest='inplace',
                        help='Replace source files')
    parser.add_argument('--workers', type=int, default=4,
                        help='Number of parallel workers (default 4)')
    parser.add_argument('--loglevel', default='ERROR',
                        help='Logging level (DEBUG|INFO|WARNING|ERROR)')

    args = parser.parse_args()

    setup_logging(args.loglevel)

    processor = ScheduleProcessor(p_workers=args.workers)
    processor.process_schedules(args.input_list, args.inplace)


if __name__ == '__main__':
    main()
