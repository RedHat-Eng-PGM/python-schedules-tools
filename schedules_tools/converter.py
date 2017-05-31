import logging
import discovery

logger = logging.getLogger(__name__)


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

    def __init__(self, schedule=None):
        self.schedule = schedule

# TODO: take a look if _get_handler* methods can't be shared for both schedule/storage
    @staticmethod
    def _get_handler_for_handle(handle):
        for module in discovery.schedule_handlers.values():
            if module['class'].is_valid_source(handle):
                return module

        msg = "Can't find schedule handler for handle: {}".format(handle)
        raise ScheduleFormatNotSupported(msg)

    @staticmethod
    def _get_handler_for_format(format):
        if format not in discovery.schedule_handlers.keys():
            msg = "Can't find schedule handler for format: {}".format(format)
            raise ScheduleFormatNotSupported(msg)

        return discovery.schedule_handlers[format]

    @staticmethod
    def _get_storage_handler_for_format(format):
        if format not in discovery.storage_handlers.keys():
            msg = "Can't find storage handler for format: {}".format(format)
            raise StorageFormatNotSupported(msg)

        return discovery.storage_handlers[format]

    @classmethod
    def _get_handler_struct(cls, handle=None, storage_handler=None, format=None):
        if format:
            handler_struct = cls._get_handler_for_format(format)
        else:
            # TODO: Remove storage handler - get_local_handle
            local_handle = handle
            if storage_handler:
                local_handle = storage_handler.get_local_handle()
            handler_struct = cls._get_handler_for_handle(local_handle)
            if storage_handler:
                storage_handler.clean_local_handle()

        return handler_struct

    @classmethod
    def _get_schedule_handler_cls(cls, *args, **kwargs):
        return cls._get_handler_struct(*args, **kwargs)['class']

    @classmethod
    def _get_storage_handler_cls(cls, *args, **kwargs):
        return cls._get_storage_handler_for_format(*args, **kwargs)['class']

# TODO: following 2 methods use storage handler only if defined
# TODO: use schedule_handler and storage_handler variable names 

# TODO: Add cleanup public method to do whatever needed (clean local handle,..)
# Use lazy loading to get storage_handler / local handle to tell if it needs to be cleaned

    # Following methods call their counterparts on handlers
    def handle_modified_since(self, handle, mtime,
                              src_format=None, handler_opt_args=dict()):
        """ Return boolean (call schedule_handler specific method) to be able to bypass processing """
        # TODO: same logic as import_schedule regarding provide_mtime
        schedule_handler_cls = self._get_schedule_handler_cls(handle=handle, format=src_format)

        schedule_handler = schedule_handler_cls(handle=handle, opt_args=handler_opt_args)

        return schedule_handler.handle_modified_since(mtime)

    def import_schedule(self, handle, source_format=None,
                        handler_opt_args=dict()):
        # it's possible that we don't need any storage handler (smartsheet)
        # if needed - create on self (lazy load - shared between methods)
        # if defined - get local handle
        storage_format = handler_opt_args.get('source_storage_format', 'local')

        storage_handler_cls = self._get_storage_handler_cls(storage_format)
        storage_handler = storage_handler_cls(
            handle=handle,
            opt_args=handler_opt_args)

        # TODO: Remove storage handler passing
        # create schedule handler in one step - directly instance?
        # use LOCAL handle if available, otherwise use passed handle
        schedule_handler_cls = self._get_schedule_handler_cls(handle=handle,
                                           storage_handler=storage_handler,
                                           format=source_format)
        schedule_handler = schedule_handler_cls(handle=handle,
                              src_storage_handler=storage_handler,
                              opt_args=handler_opt_args)

        schedule = schedule_handler.import_schedule()  # should import changelog if possible
        
        # if storage defined and provides changelog/mtime - use storage handler to overwrite it

        assert schedule is not None, 'Import schedule_handler {} didn\'t return filled ' \
                                     'schedule!'.format(schedule_handler_cls)
        self.schedule = schedule
        return self.schedule

    def export_schedule(self, output, target_format, handler_opt_args=dict()):
        tj_id = handler_opt_args.get('tj_id', '')
        v_major = handler_opt_args.get('major', '')
        v_minor = handler_opt_args.get('minor', '')
        v_maint = handler_opt_args.get('maint', '')

        handler_cls = self._get_schedule_handler_cls(format=target_format)

        if not handler_cls.provide_export:
            raise HandleWithoutExport(
                'Schedule handler for {} doesn\'t provide export.'
                .format(target_format))

        handler = handler_cls(schedule=self.schedule, opt_args=handler_opt_args)

        handler.schedule.override_version(tj_id, v_major, v_minor, v_maint)

        handler.export_schedule(output)
