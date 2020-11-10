#!/usr/bin/env python3

import argparse
import sys
import logging
from schedules_tools.converter import get_handlers_args_parser, convert


logger = logging.getLogger(__name__)


def setup_logging(level):
    log_format = '%(name)-10s %(levelname)7s: %(message)s'
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(level)

    formatter = logging.Formatter(log_format)
    sh.setFormatter(formatter)

    # setup root logger
    inst = logging.getLogger('')
    inst.setLevel(level)
    inst.addHandler(sh)


def main():
    parser = argparse.ArgumentParser(description='Convert schedules source to target',
                                     parents=[get_handlers_args_parser()])

    parser.add_argument('source',
                        help='Source handle (file/URL/...)',
                        type=str,
                        metavar='SRC')

    parser.add_argument('target', metavar='TARGET',
                        help='Output target', default=None, nargs='?')

    args = parser.parse_args()

    setup_logging(getattr(logging, args.log_level))

    convert(args)


if __name__ == '__main__':
    main()
