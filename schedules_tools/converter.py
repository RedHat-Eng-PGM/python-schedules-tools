import logging
import os

from schedules_tools import discovery
from schedules_tools import SchedulesToolsException
from schedules_tools.discovery import search_paths
from schedules_tools.models import Schedule
from schedules_tools.storage_handlers import AcquireLockException


log = logging.getLogger(__name__)


SORT_FIELDS = {
    'name': 'name',
    'date_start': 'dStart',
    'date_finish': 'dFinish',
    'source': None,
}


class ScheduleFormatNotSupported(Exception):
    pass


class StorageFormatNotSupported(Exception):
    pass


class HandleWithoutExport(Exception):
    pass


class HandlerMissingDeps(Exception):
    pass


class ScheduleConverter(object):
    """
    Abstraction class to work with handles/schedules
    no matter the exact handler/schedule type.
    """
    schedule = None
    storage_handler = None
    local_handle = None

    def __init__(self, schedule=None):
        self.schedule = schedule

    # TODO: take a look if _get_handler* methods can't be shared for both
    # schedule/storage
    @staticmethod
    def _get_schedule_handler_for_handle(handle):
        for module in discovery.schedule_handlers.values():
            if module['class'].handle_deps_satisfied and module['class'].is_valid_source(handle):
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
        """Prepare storage handler if it's necessary and isn't already prepared"""
        if storage_src_format and not self.storage_handler:
            storage_handler_cls = self._get_storage_handler_cls(storage_src_format)
            storage_handler = storage_handler_cls(handle=handle,
                                                  options=options)
            self.storage_handler = storage_handler
        
        return self.storage_handler

    def _get_local_handle_from_storage(self, handle, storage_src_format, options):
        """Init storage and get local handle from storage if specified otherwise return original handle"""
        if not self.local_handle:
            self.local_handle = handle
    
            self._init_storage_handler(handle, storage_src_format, options)
            
            if self.storage_handler:
                self.local_handle = self.storage_handler.get_local_handle()

        return self.local_handle

    def cleanup_local_handle(self):
        if self.storage_handler:
            self.storage_handler.clean_local_handle()
        
        self.local_handle = None

    # Following methods call their counterparts on handlers
    def handle_modified_since(self, 
                              handle, 
                              mtime,
                              schedule_src_format=None, 
                              storage_src_format=None,
                              cleanup=True,
                              options=dict()
                              ):
        """ Return boolean (call schedule_handler specific method) to be able to bypass processing """
        errors = []
        handle_modified = True

        self._init_storage_handler(handle, storage_src_format, options)

        # use storage if possible, otherwise schedule
        if self.storage_handler and self.storage_handler.provide_mtime:
            handle_modified = self.storage_handler.handle_modified_since(mtime)
        else:
            local_handle = self._get_local_handle_from_storage(handle, 
                                                               storage_src_format,
                                                               options
                                                               )        

            schedule_handler_cls = self._get_schedule_handler_cls(
                                            handle=local_handle, 
                                            format=schedule_src_format
                                            )

            if not schedule_handler_cls.handle_deps_satisfied:
                msg = ('Schedule handler {} has unsatisfied dependencies, '
                       'can\'t get modified time.'.format(schedule_handler_cls))
                raise HandlerMissingDeps(msg)
    
            try:
                handle_modified = schedule_handler_cls(handle=local_handle, 
                                                       options=options
                                                       ).handle_modified_since(mtime)
            except SchedulesToolsException as e:
                error_item = e.__class__.__name__, str(e).split('\n'), e.source
                errors.append(error_item)
            
            if cleanup:
                self.cleanup_local_handle()
            
        return handle_modified, errors

    def import_schedule(self,
                        handle, 
                        schedule_src_format=None,
                        storage_src_format=None,
                        cleanup=True,
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
        if not schedule_handler_cls.handle_deps_satisfied:
            msg = ('Schedule handler {} has unsatisfied dependencies, '
                   'can\'t import schedule.'.format(schedule_handler_cls))
            raise HandlerMissingDeps(msg)

        schedule_handler = schedule_handler_cls(
                                        handle=local_handle, 
                                        options=options
                                        )

        # imports changelog and mtime - if implemented
        schedule = Schedule()
        try:
            schedule = schedule_handler.import_schedule()

            # if storage defined and provides changelog/mtime - use storage handler to overwrite it
            if self.storage_handler:
                if self.storage_handler.provide_changelog:
                    schedule.changelog = self.storage_handler.get_handle_changelog()

                if self.storage_handler.provide_mtime:
                    schedule.mtime = self.storage_handler.get_handle_mtime()

        except SchedulesToolsException as e:
            error_item = e.__class__.__name__, str(e).split('\n'), e.source
            schedule.errors_import.append(error_item)

        self.schedule = schedule
        
        if cleanup:
            self.cleanup_local_handle()
        
        return self.schedule

    def export_schedule(self, output, target_format, update_filename=False, options=dict()):
        schedule_slug = options.get('slug', '')

        schedule_handler_cls = self._get_schedule_handler_cls(format=target_format)

        if not schedule_handler_cls.provide_export:
            raise HandleWithoutExport(
                'Schedule handler for {} doesn\'t provide export.'
                .format(target_format))

        if not schedule_handler_cls.handle_deps_satisfied:
            msg = ('Schedule handler {} has unsatisfied dependencies, '
                   'can\'t export schedule.'.format(schedule_handler_cls))
            raise HandlerMissingDeps(msg)

        schedule_handler = schedule_handler_cls(schedule=self.schedule, options=options)
        
        if update_filename and schedule_handler.default_export_ext:  # change/add export extension according to handler
            output = '.'.join([os.path.splitext(output)[0], 
                               schedule_handler.default_export_ext])

        return schedule_handler.export_schedule(output)

        

def convert(args):
    opt_args = vars(args)
    
    # set timezone - it's desirable that all calculations are made in same TZ
    os.environ['TZ'] = opt_args['tz']
    
    for path in opt_args.pop('handlers_path'):
        search_paths.append(path)

    converter = ScheduleConverter()

    try:
        converter.import_schedule(handle=args.source,
                                  schedule_src_format=args.source_format,
                                  storage_src_format=args.source_storage_format,
                                  options=opt_args)

        if converter.schedule.errors_import:
            for err in converter.schedule.errors_import:
                msg = '{} Handle: {}\n{}'.format(err[0], err[2], '\n'.join(err[1]))
                log.error(msg)
            return False
        
    except AcquireLockException as e:
        log.error(e)
        return

    check_tasks = dict()
    for task_name in args.check_taskname:
        check_tasks[task_name] = False

    for task_name in args.check_taskname_startswith:
        check_tasks[task_name] = True

    if args.check_taskname or args.check_taskname_startswith:
        missing_tasks = converter.schedule.check_for_taskname(check_tasks)
        if missing_tasks:
            log.info('Missing tasks: {}'.format(list(missing_tasks)))

    if args.flat or args.milestones:
        converter.schedule.make_flat()
        
    if args.milestones:
        converter.schedule.filter_milestones()

    if args.sort:
        converter.schedule.sort_tasks(args.sort)
        
    flag_show = args.flag_show.split(',')
    if flag_show == ['']:
        flag_show = []        

    flag_hide = [f for f in args.flag_hide.split(',') if f]
    if flag_hide == ['']:
        flag_hide = []  
        
    converter.schedule.filter_flags(flag_show, flag_hide)      


    # do we have target name defined?
    update_filename = False
    if not args.target:
        args.target = args.source
        update_filename = True

    converter.export_schedule(args.target,
                              args.target_format,
                              update_filename=update_filename,
                              options=opt_args)   


def get_handlers_args_parser(add_help=False):
    """Return parent parser for schedules tools scripts with handler arguments"""
    import argparse 
    
    parser = argparse.ArgumentParser(add_help=add_help)
    
    parser.add_argument('--log-level',
                        help='ERROR (default) | WARN | INFO | DEBUG',
                        default='ERROR')

    parser.add_argument('--handlers-path', 
                        help='Add python-dot-notation path to discover handlers (needs to '
                             'be python module), can be called several times '
                             '(conflicting names will be overriden - the last '
                             'implementation will be used)',
                        action='append',
                        default=[],
                        )

    parser.add_argument('-f', '--force',
                        help='Force target overwrite',
                        default=False,
                        action='store_true')

    parser.add_argument('--slug', metavar='SCHEDULE_SLUG',
                        help='Override schedule slug (e.g. rhel)')
    parser.add_argument('--use-tji-file',
                        help='Use TJI file when exporting into TJP',
                        default=False,
                        action='store_true')
    parser.add_argument('--tjp-keep-tjx',
                        help='Keep tjx intermediate file when importing from TJP',
                        default=False,
                        action='store_true')

    parser.add_argument('--rally-iter', help='Rally iteration to import',
                        default='')

    parser.add_argument('--check-taskname',
                        help='Check existence given task name as exact match '
                             '(can be used multiple times)',
                        action='append', metavar='TASKNAME', default=[])
    parser.add_argument('--check-taskname-startswith',
                        help='Check existence given task by matching beginning '
                             'name (can be used multiple times)',
                        action='append', metavar='TASKNAME_STARTSWITH',
                        default=[])

    parser.add_argument('--source-storage-format',
                        choices=discovery.storage_handlers.keys(),
                        metavar='SRC_STORAGE_FORMAT',
                        help='Source storage format to use')
    
    parser.add_argument('--cvs-repo-name',
                        help='Name of CVS repository to checkout')
    parser.add_argument('--cvs-root',
                        help='Root of CVS repository')
    parser.add_argument('--cvs-checkout-path',
                        help='Path to shared working copy of CVS repository')
    parser.add_argument('--cvs-exclusive-access',
                        help='Restrict to run just one CVS command at the same time',
                        action='store_true')
    parser.add_argument('--cvs-lock-redis-uri',
                        help='Redis URI that is required by --cvs-exclusive-access, default: localhost:6379/0',
                        default='localhost:6379/0')
    
    parser.add_argument('--smartsheet-token',
                        help='Access token for using SmartSheet API')
    
    parser.add_argument('--date-format',
                        help='Date format used for export where applicable')    

    parser.add_argument('--html-title',
                        help='HTML export page title')    
    parser.add_argument('--html-table-header',
                        help='HTML export table header')    

    
    parser.add_argument('--flat',
                        help='Make output schedule flat',
                        default=False,
                        action='store_true')

    parser.add_argument('--milestones',
                        help='Filter only milestones (implies --flat)',
                        default=False,
                        action='store_true')
    
    parser.add_argument('--flag-show',
                        help='Filter schedule - show tasks with any of these flags',
                        default='',
                        )
    parser.add_argument('--flag-hide',
                        help='Filter schedule - hide tasks with any of these flags, hide has preferrence over show',
                        default='',
                        )


    parser.add_argument('--source-format',
                        metavar='SRC_FORMAT',
                        help='Source format to enforce')

    parser.add_argument('--target-format',
                        metavar='TARGET_FORMAT',
                        help='Target format to convert',
                        default='html')
    
    parser.add_argument('--tz',
                        help='Timezone used for schedule conversions (default "America/New_York")',
                        default='America/New_York')

    def sorting_field(value):
        try:
            field = SORT_FIELDS[value]
        except KeyError:
            raise argparse.ArgumentTypeError('"%s" is not a valid sorting value' % value)

        return field

    parser.add_argument('--sort',
                        help='Sort by: %s' % ', '.join(SORT_FIELDS.keys()),
                        type=sorting_field)
    
    return parser
