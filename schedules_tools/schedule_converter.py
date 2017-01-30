#!/usr/bin/env python
import argparse
import os
import sys
import re
import handlers
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(name)s %(levelname)7s: %(message)s'
)

logger = logging.getLogger('pp.core')
VALID_MODULE_NAME = re.compile(r'[_a-z]\w*\.py$', re.IGNORECASE)
BASE_DIR = os.path.dirname(os.path.realpath(
    os.path.join(__file__, os.pardir)))
PARENT_DIRNAME = os.path.basename(os.path.dirname(os.path.realpath(__file__)))

# FIXME(mpavlase): Figure out nicer way to deal with paths
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, PARENT_DIRNAME))


class ScheduleFormatNotSupported(Exception):
    pass


class HandleWithoutExport(Exception):
    pass


class AutodiscoverHandlers(object):
    _top_level_dir = os.path.join(BASE_DIR, PARENT_DIRNAME)

    def _get_name_from_path(self, path):
        path = os.path.splitext(os.path.normpath(path))[0]

        relpath = os.path.relpath(path, self._top_level_dir)
        assert not os.path.isabs(relpath), "Path must be within the project"
        assert not relpath.startswith('..'), "Path must be within the project"

        name = relpath.replace(os.path.sep, '.')
        return name

    @staticmethod
    def _get_module_from_name(name):
        __import__(name)
        return sys.modules[name]

    @staticmethod
    def _find_classes(module):
        ret = dict()

        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and issubclass(obj, handlers.ScheduleHandlerBase):
                pieces = obj.__name__.split('_')
                if len(pieces) < 2:
                    continue

                val = dict()
                key = pieces[-1]
                val['class'] = obj
                val['provide_export'] = obj.provide_export

                ret[key] = val
        return ret

    def discover(self, start_dir):
        paths = os.listdir(start_dir)
        ret = {}

        for path in paths:
            full_path = os.path.join(start_dir, path)
            
            if os.path.isfile(full_path):
                if not VALID_MODULE_NAME.match(path):
                    # valid Python identifiers only
                    continue
                
                name = self._get_name_from_path(full_path)
                module = self._get_module_from_name(name)
                classes = self._find_classes(module)
            
                for k in classes.keys():
                    if k in ret.keys():
                        msg = ('Found duplicated handler name (would be '
                               'overrriden): {} ({}, {})').format(
                            k, ret[k], classes[k])
                        logger.warning(msg)

                ret.update(classes)
        
        return ret


class ScheduleConverter(object):
    handlers_dir = 'handlers'
    handlers = {}
    provided_exports = []
    schedule = None

    def __init__(self):
        ad = AutodiscoverHandlers()
        #handlers_path = os.path.join(BASE_DIR, self.handlers_dir)
        handlers_path = os.path.join(BASE_DIR, PARENT_DIRNAME, self.handlers_dir)
        self.handlers = ad.discover(handlers_path)

        for key, val in self.handlers.iteritems():
            if val['provide_export']:
                self.provided_exports.append(key)

    def find_handle(self, handle):
        for k, mod in self.handlers.iteritems():
            if mod['class'].is_valid_source(handle):
                return mod

        msg = ('Given schedule format doesn\'t match any of available '
               'handlers: {}').format(handle)
        raise ScheduleFormatNotSupported(msg)

    def import_schedule(self, handle, handler_opt_args=dict()):
        handle_class = self.find_handle(handle)['class']
        handle_inst = handle_class(opt_args=handler_opt_args)
        sch = handle_inst.import_schedule(handle)
        self.schedule = sch
        return self.schedule

    def _get_export_handle_cls(self, target_format):
        handle_class = self.handlers[target_format]['class']
        if not handle_class.provide_export:
            raise HandleWithoutExport(
                'Handler {} doesn\'t provide export method for this format.'
                .format(target_format))

        return handle_class

    def export_handle(self, target_format, out_file, handler_opt_args=dict()):
        tj_id = handler_opt_args['tj_id']
        v_major = handler_opt_args['major']
        v_minor = handler_opt_args['minor']
        v_maint = handler_opt_args['maint']

        handle_class = self._get_export_handle_cls(target_format)
        handle_inst = handle_class(schedule=self.schedule,
                                   opt_args=handler_opt_args)

        handle_inst.schedule.override_version(
            tj_id, v_major, v_minor, v_maint)

        handle_inst.export_schedule(out_file)

if __name__ == '__main__':
    converter = ScheduleConverter()
    parser = argparse.ArgumentParser(description='Perform schedule conversions.')

    parser.add_argument('--tj-id', metavar='TJ_PROJECT_ID',
                        help='TJ Project Id (e.g. rhel)')
    parser.add_argument('--major', help='Project major version number',
                        default='')
    parser.add_argument('--minor', help='Project minor version number',
                        default='')
    parser.add_argument('--maint', help='Project maint version number',
                        default='')
    parser.add_argument('--rally-iter', help='Rally iteration to import',
                        default='')

    parser.add_argument('source', type=str,
                        help='Source of schedule (file/URL/...)')
    parser.add_argument('target_format',
                        choices=converter.provided_exports,
                        metavar='TARGET_FORMAT',
                        help='Target format to convert')
    parser.add_argument('out_file', metavar='OUT_FILE',
                        help='Output schedule file', default=None, nargs='?')

    arguments = parser.parse_args()
    opt_args = vars(arguments)
    converter.import_schedule(arguments.source, handler_opt_args=opt_args)

    converter.export_handle(arguments.target_format,
                            arguments.out_file,
                            handler_opt_args=opt_args)
