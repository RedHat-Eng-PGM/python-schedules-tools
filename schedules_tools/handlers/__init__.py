from datetime import datetime
import logging
import time
import os

from lxml import etree

logger = logging.getLogger(__name__)


# Handle implementation must be in format ScheduleHandler_format
# where 'format' is used as a uniq label for the format and
# 'ScheduleHandler' can be whatever.
class ScheduleHandlerBase(object):
    handle = None
    schedule = None
    
    # optional source storage handler instance to get changelog/mtime from if applicable
    # TODO: REMOVE!!
    src_storage_handler = None

    # This flag indicate ability to export internal intermediate structure
    # (Schedule) into format of implementation. It's read by ScheduleConverter
    # during autodiscovery and used to provide actual help message in CLI
    
    # TODO: add provide_import to be complete? 
    provide_export = False
    provide_changelog = False
    provide_mtime = False
    
    opt_args = {}

    def __init__(self, handle=None, schedule=None, src_storage_handler=None, 
                 opt_args=dict()):
        from schedules_tools.converter import ScheduleConverter

        self.handle = handle  # 'handle' is source/target of schedule in general
        self.schedule = schedule

        self.opt_args = opt_args

        if src_storage_handler: 
            self.src_storage_handler = src_storage_handler
        else:  # Use local storage handler as default
            local_storage_handler_cls = ScheduleConverter.get_storage_handler_cls('local')
            self.src_storage_handler = local_storage_handler_cls(
                                            handle=self.handle,
                                            opt_args=self.opt_args)

        if self.handle:
            self.src_storage_handler.handle = self.handle
        

    def _write_to_file(self, content, file):
        with open(file, 'wb') as fp:
            fp.write(content.strip().encode('UTF-8'))

    def get_handle_mtime(self):
        # TODO: NotImplement by default, if possible to tell without storage - implement directly
        return self.src_storage_handler.get_handle_mtime()
    
    def handle_modified_since(self, mtime):
        """ Return boolean to be able to bypass processing """
        # Return False only when able to tell otherwise return True
        if isinstance(mtime, datetime):
            handle_mtime = self.get_handle_mtime()
            if handle_mtime and handle_mtime <= mtime:
                return False
        
        return True
  
    def _get_handle_changelog_from_content(self):
        # TODO: remove - if possible, changelog is get in get_handle_changelog
        raise NotImplementedError   
    
    def get_handle_changelog(self):
        # TODO: Not implemented by default
        # When handler can get changelog - implement it in this method, not *_from _content
        if self.src_storage_handler.provide_changelog:
            return self.src_storage_handler.get_handle_changelog()
        elif self.provide_changelog:
            return self._get_handle_changelog_from_content()
        
        # Maybe raise Exception and handle it on higher level?        
        return {}
            
                
    # handle - file/link/smartsheet id
    def import_schedule(self):
        raise NotImplementedError

    def export_schedule(self):
        raise NotImplementedError   
    
    def build_schedule(self):
        raise NotImplementedError 

    @classmethod
    def is_valid_source(cls, handle=None):
        """Method returns True, if the specific handler is able to work with
        given handle"""
        return False

    def extract_backup(self, handle=None):
        """Prepare files which need a backup in case of external source"""
        return []


class TJXCommonMixin(object):   
    src_tree = None
    provide_changelog = True
    
    def _get_parsed_tree(self):
        if not self.src_tree:
            self.src_tree = etree.parse(self.handle)
        
        return self.src_tree
    
    def _get_handle_changelog_from_content(self):
        # import changelog
        changelog = {}
        
        for log in self._get_parsed_tree().xpath('changelog/log'):
            changelog[log.get('rev')] = {
                'date': datetime.strptime(log.get('date'), '%Y/%m/%d'),
                'user': log.get('user'),
                'msg': log.text.strip(),
            }
            
        return changelog

