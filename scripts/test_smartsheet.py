#!/usr/bin/env python3

import os
import sys
import logging
from schedules_tools.schedule_handlers.smart_sheet import ScheduleHandler_smartsheet
from multiprocessing import Pool


ss = ScheduleHandler_smartsheet(
    options=dict(smartsheet_token=os.getenv('SMARTSHEET_TOKEN', '')))


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


def do_req(worker):
    for i in range(1, 80):
        cont = ss.client.Sheets.list_sheets(include_all=True)
        cont = str(cont)
        if 'Rate limit' in cont:
            print(worker, i)


if __name__ == '__main__':
    setup_logging(logging.WARNING)
    workers = 10

    p = Pool(workers)
    p.map(do_req, range(1, 1 + workers))
