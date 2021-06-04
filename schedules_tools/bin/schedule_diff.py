#!/usr/bin/env python3

"""
Simple wrapper to get diff of two schedules

It's able to show different attributes (by 'attrs' kwarg)
and indicate missing phases

Follows 'diff' exit codes:
    0 - same
    1 - different
    2 - other trouble
"""

import argparse
import logging
import sys

from schedules_tools import discovery
from schedules_tools.diff import ScheduleDiff

import schedules_tools.converter as conv


def setup_logging(level):
    log_format = '%(name)-10s %(levelname)7s: %(message)s'
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(level)

    formatter = logging.Formatter(log_format)
    sh.setFormatter(formatter)

    # setup root logger
    inst = logging.getLogger('')
    inst.setLevel(level)
    inst.addHandler(sh)


def main():
    setup_logging(logging.DEBUG)
    parser = argparse.ArgumentParser(
        description='Tool to show differences between two schedules.')

    parser.add_argument('--simple-diff',
                        help='Simple comparison between two schedules.',
                        action='store_true',
                        default=False)

    parser.add_argument(
        '--handlers-path',
        help='Add python-dot-notation path to discover handlers (needs to '
             'be python module), can be called several times '
             '(conflicting names will be overriden - the last '
             'implementation will be used)',
        action='append',
        default=[])
    parser.add_argument('--whole-days',
                        help='Compare just date part of timestamp (will '
                             'ignore differences in time)',
                        action='store_true',
                        default=False)
    parser.add_argument('left')
    parser.add_argument('right')
    args = parser.parse_args()

    for path in args.handlers_path:
        discovery.search_paths.append(path)

    left = conv.ScheduleConverter()
    left.import_schedule(args.left)

    right = conv.ScheduleConverter()
    right.import_schedule(args.right)

    if args.simple_diff:
        diff_res = left.schedule.diff(right.schedule, whole_days=args.whole_days)
    else:
        diff_res = ScheduleDiff(left.schedule, right.schedule)

    if diff_res:
        print(diff_res)
        sys.exit(1)


if __name__ == '__main__':
    main()
