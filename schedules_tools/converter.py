import os
import sys
import re
import logging
import discovery


VALID_MODULE_NAME = re.compile(r'^(\w+)\.py$', re.IGNORECASE)
BASE_DIR = os.path.dirname(os.path.realpath(
    os.path.join(__file__, os.pardir)))
PARENT_DIRNAME = os.path.basename(os.path.dirname(os.path.realpath(__file__)))

logger = logging.getLogger(__name__)
re_schedule_handler = re.compile('^ScheduleHandler_(\S+)$')
re_storage_handler = re.compile('^ScheduleStorageHandler_(\S+)$')

# FIXME(mpavlase): Figure out nicer way to deal with paths
sys.path.append(BASE_DIR)


class ScheduleFormatNotSupported(Exception):
    pass


class StorageFormatNotSupported(Exception):
    pass


class HandleWithoutExport(Exception):
    pass


class ScheduleConverter(object):
    """
    Abstraction class to work with handles/schedules
    no matter the exact handler/schedule type.
    """
    schedule = None
    schedule_handlers_dir = 'handlers'
    schedule_handlers = {}
    schedule_discovery = None
    provided_exports = []
    storage_handlers_dir = 'storage'
    storage_handlers = {}
    storage_discovery = None

    def __init__(self, schedule=None):
        schedule_handlers_path = os.path.join(BASE_DIR, PARENT_DIRNAME, self.schedule_handlers_dir)
        storage_handlers_path = os.path.join(BASE_DIR, PARENT_DIRNAME, self.storage_handlers_dir)

        self.schedule_discovery = discovery.AutodiscoverHandlers(re_schedule_handler)
        self.storage_discovery = discovery.AutodiscoverHandlers(re_storage_handler)

        self.add_discover_path(schedule_handlers_path)
        self.add_discover_path(storage_handlers_path)

        self.schedule = schedule

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
        self.schedule_handlers = self.schedule_discovery.discover(handlers_path)
        self.storage_handlers = self.storage_discovery.discover(handlers_path)

        self.provided_exports = []
        
        for handler_name, handler in self.schedule_handlers.iteritems():
            if handler['provide_export']:
                self.provided_exports.append(handler_name)

        self.provided_exports = sorted(self.provided_exports)

    def get_handler_for_handle(self, handle, storage_handle):
        handle_local = handle
        if storage_handle:
            handle_local = storage_handle.get_local_handle(handle)

        for module in self.schedule_handlers.itervalues():
            if module['class'].is_valid_source(handle_local):
                return module

        msg = "Can't find schedule handler for handle: {}".format(handle)
        raise ScheduleFormatNotSupported(msg)

    def get_handler_for_format(self, format, storage_handle):
        if format not in self.schedule_handlers:
            msg = "Can't find schedule handler for format: {}".format(format)
            raise ScheduleFormatNotSupported(msg)

        return self.schedule_handlers[format]

    def get_storage_handler_for_format(self, format):
        if format not in self.storage_handlers:
            msg = "Can't find storage handler for format: {}".format(format)
            raise StorageFormatNotSupported(msg)

        return self.storage_handlers[format]

    def get_handler(self, handle=None, format=None, storage_handler=None):
        if format:
            handler_struct = self.get_handler_for_format(format, storage_handler)
        else:
            handler_struct = self.get_handler_for_handle(handle, storage_handler)

        return handler_struct

    def get_handler_cls(self, *args, **kwargs):
        return self.get_handler(*args, **kwargs)['class']

    # Following methods call their counterparts on handlers
    def handle_modified_since(self, handle, mtime,
                              src_format=None, handler_opt_args=dict()):
        handler_cls = self.get_handler_cls(handle=handle, format=src_format)

        handler = handler_cls(handle=handle, opt_args=handler_opt_args)

        return handler.handle_modified_since(mtime)

    def import_schedule(self, handle, source_format=None, handler_opt_args=dict()):
        src_storage_format = handler_opt_args.get('source_storage_format', None)
        if src_storage_format:
            storage_handler_struct = self.get_storage_handler_for_format(src_storage_format)
            storage_handler_cls = storage_handler_struct['class']
            storage_handler = storage_handler_cls(opt_args=handler_opt_args)
            storage_handler.clone()
            storage_handler.build_handle(handle)
        else:
            storage_handler = None

        handler_cls = self.get_handler_cls(handle=handle,
                                           format=source_format,
                                           storage_handler=storage_handler)
        handler = handler_cls(handle=handle,
                              src_storage_handler=storage_handler,
                              opt_args=handler_opt_args)

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
