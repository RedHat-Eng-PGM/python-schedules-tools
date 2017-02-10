#!/usr/bin/env python
import argparse
import os
import sys
import re
import handlers
import logging
import importlib

logger = logging.getLogger(__name__)
handler_class_template = re.compile('^ScheduleHandler_(\S+)$')
VALID_MODULE_NAME = re.compile(r'^(\w+)\.py$', re.IGNORECASE)
BASE_DIR = os.path.dirname(os.path.realpath(
    os.path.join(__file__, os.pardir)))
PARENT_DIRNAME = os.path.basename(os.path.dirname(os.path.realpath(__file__)))

# FIXME(mpavlase): Figure out nicer way to deal with paths
sys.path.append(BASE_DIR)


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


class ScheduleFormatNotSupported(Exception):
    pass


class HandleWithoutExport(Exception):
    pass


class AutodiscoverHandlers(object):
    _discovered_handlers = dict()

    def _load_parent_module(self, path):
        realpath = os.path.realpath(path)
        parent = os.path.dirname(realpath)
        module_name = os.path.basename(realpath)
        if parent not in sys.path:
            logger.info('Add path {} to sys.path (as parent of {})'.format(parent, path))
            sys.path.append(parent)
        importlib.import_module(module_name)

        return module_name

    @staticmethod
    def _load_module(name):
        importlib.import_module(name)
        return sys.modules[name]

    @staticmethod
    def _find_classes(module):
        ret = dict()

        for name in dir(module):
            obj = getattr(module, name)
            is_inst = isinstance(obj, type)

            if not is_inst:
                continue

            if obj == handlers.ScheduleHandlerBase:
                continue

            # TODO(mpavlase): figure out more reliable way to test subclasses
            #is_subclass = issubclass(obj, handlers.ScheduleHandlerBase)
            #if not is_subclass:
            #    continue

            key = re.findall(handler_class_template, obj.__name__)
            if not key:
                continue

            key = key[0]
            val = dict()
            val['class'] = obj
            val['provide_export'] = obj.provide_export

            ret[key] = val
            logger.debug('Discovered new handler: {} from {}'.format(key, module))
        return ret

    def _discover_path(self, filename, parent_module):
        # valid Python identifiers only
        if not VALID_MODULE_NAME.match(filename):
            return

        name = VALID_MODULE_NAME.sub('\\1', filename)
        name = '.'.join([parent_module, name])
        module = self._load_module(name)
        classes = self._find_classes(module)

        for k in classes.keys():
            if k in self._discovered_handlers.keys():
                cls_existing = self._discovered_handlers[k]
                cls_new = classes[k]
                msg = ('Found handler with same name (would be '
                       'overridden): {} (existing: {}, new: {})').format(
                    k, cls_existing, cls_new)
                logger.info(msg)

        self._discovered_handlers.update(classes)

    def discover(self, start_dir):
        start_dir = os.path.expanduser(start_dir)
        try:
            module_name = self._load_parent_module(start_dir)
        except ImportError as e:
            logger.warn('Skipping path "{}", couldn\'t load it: {} (search '
                        'paths: {})'.format(start_dir, e, sys.path))
            return self._discovered_handlers

        files = os.listdir(start_dir)

        for filename in files:
            self._discover_path(filename, module_name)

        return self._discovered_handlers


class ScheduleConverter(object):
    """
    Abstraction class to work with handles/schedules 
    no matter the exact handler/schedule type.
    """
    handlers_dir = 'handlers'
    handlers = {}
    provided_exports = []
    schedule = None
    discovery = None


    def __init__(self):
        handlers_path = os.path.join(BASE_DIR, PARENT_DIRNAME, self.handlers_dir)
        self.discovery = AutodiscoverHandlers()
        self.add_discover_path(handlers_path)


    def add_discover_path(self, handlers_path):
        """
        Adds location in handlers_path variable to discovery path and starts to
        search for handlers. This method can be called multiple times, if there
        will be conflict in name of the handler, discovered implementation will
        be used (override the old one).

        Order of search paths:
         - schedules_tools/handlers
         - handlers_path (optionally)

        Args:
            handlers_path: Path to directory (python module) to search for handlers
        """
        logger.debug('Searching for handlers in path: {}'.format(handlers_path))
        self.handlers = self.discovery.discover(handlers_path)

        self.provided_exports = []
        
        # TODO: Don't use "key, val" when it has a meaning
        for key, val in self.handlers.iteritems():
            if val['provide_export']:
                self.provided_exports.append(key)
                
        self.provided_exports = sorted(self.provided_exports)


    def get_handler_for_handle(self, handle):
        # TODO: what is mod and why don't you use itervalues ?
        for k, mod in self.handlers.iteritems():
            if mod['class'].is_valid_source(handle):
                return mod

        msg = "Can't find schedule handler for handle: {}".format(handle)
        raise ScheduleFormatNotSupported(msg)

    def get_handler_for_format(self, format):
        if format not in self.handlers:
            msg = "Can't find schedule handler for format: {}".format(format)
            raise ScheduleFormatNotSupported(msg)
            
        return self.handlers[format]
    
    def get_handler(self, handle=None, format=None):
        if format:
            handler_cls = self.get_handler_for_format(format)
        else:
            handler_cls = self.get_handler_for_handle(handle)
            
        return handler_cls
    
    def get_handler_cls(self, *args, **kwargs):
        return self.get_handler(*args, **kwargs)['class']

    # Following methods call their counterparts on handlers

    def handle_modified_since(self, handle, mtime, 
                              src_format=None, handler_opt_args=dict()):
        handler_cls = self.get_handler_cls(handle=handle, format=src_format)
            
        handler = handler_cls(handle=handle, opt_args=handler_opt_args)

        return handler.handle_modified_since(mtime)
    

    def import_schedule(self, handle, source_format=None, handler_opt_args=dict()):
        handler_cls = self.get_handler_cls(handle=handle, format=source_format)
            
        handler = handler_cls(handle=handle, opt_args=handler_opt_args)
        
        schedule = handler.import_schedule()
        
        assert schedule is not None, 'Import handler {} didn\'t return filled ' \
                                     'schedule!'.format(handler_cls)
        self.schedule = schedule
        return self.schedule


    def export_schedule(self, output, target_format, handler_opt_args=dict()):
        tj_id = handler_opt_args.get('tj_id', '')
        v_major = handler_opt_args.get('major', '')
        v_minor = handler_opt_args.get('minor', '')
        v_maint = handler_opt_args.get('maint', '')

        handler_cls = self.get_handler_cls(format=target_format)
        
        if not handler_cls.provide_export:
            raise HandleWithoutExport(
                'Schedule handler for {} doesn\'t provide export.'
                .format(target_format))
        
        handler = handler_cls(schedule=self.schedule, opt_args=handler_opt_args)

        handler.schedule.override_version(tj_id, v_major, v_minor, v_maint)

        handler.export_schedule(output)



def main(args):
    handlers_args_def = '--handlers-path',
    handlers_kwargs_def = {
        'help': 'Add path to discover handlers (needs to be python'
                ' module), can be called several times '
                '(conflicting names will be overriden - the last '
                'implementation will be used)',
        'action': 'append',
        'default': []
    }
    setup_logging(logging.DEBUG)
    converter = ScheduleConverter()

    # Separate parser to handle '--handlers-path' argument and prepare
    # converter.provided_exports to be used in main parser
    add_handler_parser = argparse.ArgumentParser(add_help=False)
    add_handler_parser.add_argument(*handlers_args_def, **handlers_kwargs_def)
    known_args = add_handler_parser.parse_known_args(args)

    opt_args = vars(known_args[0])  # 0. index contains successfully parsed args
    for path in opt_args.pop('handlers_path'):
        converter.add_discover_path(path)

    parser = argparse.ArgumentParser(description='Perform schedule conversions.')

    parser.add_argument(*handlers_args_def, **handlers_kwargs_def)

    parser.add_argument('-f', '--force', 
                        help='Use TJI file when exporting into TJP',
                        default=False, 
                        action='store_true')

    parser.add_argument('--tj-id', metavar='TJ_PROJECT_ID',
                        help='TJ Project Id (e.g. rhel)')
    parser.add_argument('--major', help='Project major version number',
                        default='')
    parser.add_argument('--minor', help='Project minor version number',
                        default='')
    parser.add_argument('--maint', help='Project maint version number',
                        default='')
    parser.add_argument('--use-tji-file', 
                        help='Use TJI file when exporting into TJP',
                        default=False, 
                        action='store_true')
    
    parser.add_argument('--rally-iter', help='Rally iteration to import',
                        default='')
    
    parser.add_argument('--source-format',
                        choices=converter.provided_exports,
                        metavar='SRC_FORMAT',
                        help='Source format to enforce')
    parser.add_argument('source',
                        help='Source handle (file/URL/...)',
                        type=str,
                        metavar='SRC')
    
    parser.add_argument('target_format',
                        choices=converter.provided_exports,
                        metavar='TARGET_FORMAT',
                        help='Target format to convert')
    parser.add_argument('target', metavar='TARGET',
                        help='Output target', default=None, nargs='?')

    arguments = parser.parse_args(args)
    opt_args = vars(arguments)

    # --handlers-path argument is already procesed, it shouldn't be passed
    # as opt_args into handlers
    opt_args.pop('handlers_path')

    converter.import_schedule(arguments.source, 
                              arguments.source_format, 
                              handler_opt_args=opt_args)
    
    converter.export_schedule(arguments.target,
                              arguments.target_format,
                              handler_opt_args=opt_args)

if __name__ == '__main__':
    main(sys.argv[1:])
