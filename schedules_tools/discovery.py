import os
import sys
import re
import handlers
import logging
import importlib

VALID_MODULE_NAME = re.compile(r'^(\w+)\.py$', re.IGNORECASE)
PARENT_DIRNAME = os.path.basename(os.path.dirname(os.path.realpath(__file__)))
BASE_DIR = os.path.dirname(os.path.realpath(
    os.path.join(__file__, os.pardir)))

logger = logging.getLogger(__name__)
re_schedule_handler = re.compile('^ScheduleHandler_(\S+)$')
re_storage_handler = re.compile('^StorageHandler_(\S+)$')

# FIXME(mpavlase): Figure out nicer way to deal with paths
sys.path.append(BASE_DIR)

def get_local_path(path):
    return os.path.join(BASE_DIR, PARENT_DIRNAME, path)


class AutodiscoverHandlers(object):
    _discovered_handlers = None
    re_class_teplate = None

    def __init__(self, re_class_template):
        self.re_class_teplate = re_class_template
        self._discovered_handlers = dict()

    def get_handlers(self):
        return self._discovered_handlers

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

    def _find_classes(self, module):
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

            key = re.findall(self.re_class_teplate, obj.__name__)
            if not key:
                continue

            key = key[0]
            val = dict()
            val['class'] = obj
            try:
                val['provide_export'] = obj.provide_export
            except AttributeError:
                # Not all handlers has this attr
                # TODO(mpavlase): consider this behavior implement in subclass
                pass

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


class LazyDictDiscovery(dict):
    autodiscovery = None
    discovery_run_flag = True

    def __init__(self, *args, **kwargs):
        self.autodiscovery = AutodiscoverHandlers(kwargs.pop('cls_template'))
        self.update(dict(*args, **kwargs))  # use the free update to set keys
        super(LazyDictDiscovery, self).__init__(*args, **kwargs)

    def __getitem__(self, item):
        if not self.items() or self.discovery_run_flag:
            self.run_discovery()

        return super(LazyDictDiscovery, self).__getitem__(item)

    def keys(self):
        if not self.items() or self.discovery_run_flag:
            self.run_discovery()
        return super(LazyDictDiscovery, self).keys()

    def values(self):
        if not self.items() or self.discovery_run_flag:
            self.run_discovery()
        return super(LazyDictDiscovery, self).values()

    def _post_discovery_hook(self):
        """
        Override this method, if you need to do something after discovery has
        been processed.
        """
        pass

    def add_discover_path(self, path):
        search_paths.append(path)
        self.discovery_run_flag = True

    def run_discovery(self):
        ret = dict()

        for path in search_paths:
            logger.debug('Searching for handlers in path: {}'.format(path))
            ret = self.autodiscovery.discover(path)

        # override all existing keys/values
        self.clear()
        for key, value in ret.items():
            self[key] = value

        self._post_discovery_hook()
        self.discovery_run_flag = False
        return ret


class ScheduleHandlerDiscovery(LazyDictDiscovery):
    _provided_exports = []

    @property
    def provided_exports(self):
        if not self._provided_exports or self.discovery_run_flag:
            self.run_discovery()
        return self._provided_exports

    def _post_discovery_hook(self):
        for handler_name, handler in self.items():
            if handler['provide_export']:
                self._provided_exports.append(handler_name)

        self._provided_exports = sorted(self._provided_exports)


class StorageHandlerDiscovery(LazyDictDiscovery):
    pass

schedule_handlers = ScheduleHandlerDiscovery(cls_template=re_schedule_handler)
storage_handlers = StorageHandlerDiscovery(cls_template=re_storage_handler)

search_paths = [get_local_path('handlers'),
                get_local_path('storage')]
