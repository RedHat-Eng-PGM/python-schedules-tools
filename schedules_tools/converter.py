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

    @staticmethod
    def get_handler_for_handle(handle):
        for module in discovery.schedule_handlers.values():
            if module['class'].is_valid_source(handle):
                return module

        msg = "Can't find schedule handler for handle: {}".format(handle)
        raise ScheduleFormatNotSupported(msg)

    @staticmethod
    def get_handler_for_format(format):
        if format not in discovery.schedule_handlers.keys():
            msg = "Can't find schedule handler for format: {}".format(format)
            raise ScheduleFormatNotSupported(msg)

        return discovery.schedule_handlers[format]

    @staticmethod
    def get_storage_handler_for_format(format):
        if format not in discovery.storage_handlers.keys():
            msg = "Can't find storage handler for format: {}".format(format)
            raise StorageFormatNotSupported(msg)

        return discovery.storage_handlers[format]

    @classmethod
    def get_handler_struct(cls, handle=None, storage_handler=None, format=None):
        if format:
            handler_struct = cls.get_handler_for_format(format)
        else:
            local_handle = handle
            if storage_handler:
                local_handle = storage_handler.get_local_handle()
            handler_struct = cls.get_handler_for_handle(local_handle)
            if storage_handler:
                storage_handler.clean_local_handle()

        return handler_struct

    @classmethod
    def get_handler_cls(cls, *args, **kwargs):
        return cls.get_handler_struct(*args, **kwargs)['class']

    @classmethod
    def get_storage_handler_cls(cls, *args, **kwargs):
        return cls.get_storage_handler_for_format(*args, **kwargs)['class']

    # Following methods call their counterparts on handlers
    def handle_modified_since(self, handle, mtime,
                              src_format=None, handler_opt_args=dict()):
        handler_cls = self.get_handler_cls(handle=handle, format=src_format)

        handler = handler_cls(handle=handle, opt_args=handler_opt_args)

        return handler.handle_modified_since(mtime)

    def import_schedule(self, handle, source_format=None,
                        handler_opt_args=dict()):
        storage_format = handler_opt_args.get('source_storage_format', 'local')
        if storage_format:
            storage_handler_cls = self.get_storage_handler_cls(storage_format)
            storage_handler = storage_handler_cls(
                handle=handle,
                opt_args=handler_opt_args)
        else:
            storage_handler = None

        handler_cls = self.get_handler_cls(handle=handle,
                                           storage_handler=storage_handler,
                                           format=source_format)
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
