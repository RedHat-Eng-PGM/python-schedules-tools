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

# FIXME(mpavlase): Figure out nicer way to deal with paths
sys.path.append(BASE_DIR)


class AutodiscoverHandlers(object):
    _discovered_handlers = dict()
    re_class_teplate = None

    def __init__(self, re_class_template):
        self.re_class_teplate = re_class_template

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
