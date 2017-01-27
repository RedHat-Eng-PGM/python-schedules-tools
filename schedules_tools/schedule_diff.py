#!/usr/bin/env python
'''
Simple wrapper to get diff of two schedules
@author: mpavlase@redhat.com

It's able to show different attributes (by 'attrs' kwarg)
and indicate missing phases

Follows 'diff' exit codes:
    0 - same
    1 - different
    2 - other trouble
'''

import schedule_converter as conv
import os
import sys
import time
import argparse

# schedules are in US TZ
os.environ['TZ'] = 'America/New_York'
time.tzset()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Tool to show differences between two schedules.')
    parser.add_argument('--whole-days',
                        help='Compare just date part of timestamp (will '
                             'ignore differences in time)',
                        action='store_true',
                        default=False)
    parser.add_argument('left')
    parser.add_argument('right')
    args = parser.parse_args()

    left = conv.ScheduleConverter()
    left.import_schedule(args.left)

    right = conv.ScheduleConverter()
    right.import_schedule(args.right)

    whole_days = False
    diff = left.schedule.diff(right.schedule, whole_days=args.whole_days)
    if diff:
        print diff
        sys.exit(1)

