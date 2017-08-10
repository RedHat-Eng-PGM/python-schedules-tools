import logging
import discovery
from schedules_tools import ERR_SCHEDULE, error_container

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
    storage_handler = None

    def __init__(self, schedule=None):
        self.schedule = schedule

# TODO: take a look if _get_handler* methods can't be shared for both schedule/storage
    @staticmethod
    def _get_schedule_handler_for_handle(handle):
        for module in discovery.schedule_handlers.values():
            if module['class'].is_valid_source(handle):
                return module

        msg = "Can't find schedule handler for handle: {}".format(handle)
        raise ScheduleFormatNotSupported(msg)

    @staticmethod
    def _get_schedule_handler_for_format(format):
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
    def _get_schedule_handler_struct(cls, handle=None, format=None):
        if format:
            handler_struct = cls._get_schedule_handler_for_format(format)
        else:
            handler_struct = cls._get_schedule_handler_for_handle(handle)

        return handler_struct

    @classmethod
    def _get_schedule_handler_cls(cls, *args, **kwargs):
        return cls._get_schedule_handler_struct(*args, **kwargs)['class']

    @classmethod
    def _get_storage_handler_cls(cls, *args, **kwargs):
        return cls._get_storage_handler_for_format(*args, **kwargs)['class']


    def _init_storage_handler(self, handle, storage_src_format, options=dict()):
        """ Prepare storage handler if it's necessary and isn't already prepared """
        if self.storage_handler:
            return
        
        if storage_src_format:
            storage_handler_cls = self._get_storage_handler_cls(storage_src_format)
            storage_handler = storage_handler_cls(handle=handle,
                                                  options=options)
            self.storage_handler = storage_handler

    def _get_local_handle_from_storage(self, handle, storage_src_format, options):
        """Init storage and get local handle from storage if specified otherwise return original handle"""
        local_handle = handle

        self._init_storage_handler(handle, storage_src_format, options)
        
        if self.storage_handler:
            local_handle = self.storage_handler.get_local_handle()

        return local_handle

    def cleanup_local_handle(self):
        if self.storage_handler:
            self.storage_handler.clean_local_handle()


    # Following methods call their counterparts on handlers
    def handle_modified_since(self, 
                              handle, 
                              mtime,
                              schedule_src_format=None, 
                              storage_src_format=None,
                              options=dict()
                              ):
        """ Return boolean (call schedule_handler specific method) to be able to bypass processing """

        local_handle = self._get_local_handle_from_storage(handle, 
                                                           storage_src_format,
                                                           options
                                                           )        
        # use storage if possible, otherwise schedule
        if self.storage_handler and self.storage_handler.provide_mtime:
            mtime_providing_handler = self.storage_handler
        else:
            schedule_handler_cls = self._get_schedule_handler_cls(
                                            handle=local_handle, 
                                            format=schedule_src_format
                                            )
    
            mtime_providing_handler = schedule_handler_cls(
                                            handle=local_handle, 
                                            options=options
                                            )
            
        return mtime_providing_handler.handle_modified_since(mtime)

    def import_schedule(self,
                        handle, 
                        schedule_src_format=None,
                        storage_src_format=None,
                        options=dict()
                        ):
        
        # convert to local handle if needed
        local_handle = self._get_local_handle_from_storage(handle, 
                                                           storage_src_format,
                                                           options
                                                           )

        schedule_handler_cls = self._get_schedule_handler_cls(
                                        handle=local_handle, 
                                        format=schedule_src_format
                                        )
        schedule_handler = schedule_handler_cls(
                                        handle=local_handle, 
                                        options=options
                                        )

        # imports changelog and mtime - if implemented
        schedule = schedule_handler.import_schedule()

        # if storage defined and provides changelog/mtime - use storage handler to overwrite it
        if self.storage_handler:
            if self.storage_handler.provide_changelog:
                schedule.changelog = self.storage_handler.get_handle_changelog()
                
            if self.storage_handler.provide_mtime:
                schedule.mtime = self.storage_handler.get_handle_mtime()

        if schedule is None:
            msg = 'Import schedule_handler {} didn\'t return filled ' \
                  'schedule!'.format(schedule_handler_cls)
            logger.error(msg)
            error_container.add_error_log(ERR_SCHEDULE, msg)

        self.schedule = schedule
        return self.schedule

    def export_schedule(self, output, target_format, options=dict()):
        tj_id = options.get('tj_id', '')
        v_major = options.get('major', '')
        v_minor = options.get('minor', '')
        v_maint = options.get('maint', '')

        schedule_handler_cls = self._get_schedule_handler_cls(format=target_format)

        if not schedule_handler_cls.provide_export:
            raise HandleWithoutExport(
                'Schedule handler for {} doesn\'t provide export.'
                .format(target_format))

        schedule_handler = schedule_handler_cls(schedule=self.schedule, options=options)

        schedule_handler.schedule.override_version(tj_id, v_major, v_minor, v_maint)

        schedule_handler.export_schedule(output)
