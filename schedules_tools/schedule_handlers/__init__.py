from datetime import datetime
import logging
import pytz

from lxml import etree

log = logging.getLogger(__name__)


# Handle implementation must be in format ScheduleHandler_format
# where 'format' is used as a uniq label for the format and
# 'ScheduleHandler' can be whatever.
class ScheduleHandlerBase(object):
    handle = None
    schedule = None

    # This flag indicate ability to export internal intermediate structure
    # (Schedule) into format of implementation. It's read by ScheduleConverter
    # during autodiscovery and used to provide actual help message in CLI
    
    # TODO: add provide_import to be complete? 
    provide_export = False
    provide_changelog = False
    provide_mtime = False
    
    options = {}
    
    default_export_ext = None

    # Handlers can depend on additional python modules. We don't require from
    # users to have all of them installed if they aren't used.
    # This flag indicates that the handler can be fully utilized and there is
    # no missing dependent packages installed.
    handle_deps_satisfied = False

    def __init__(self, handle=None, schedule=None, options=dict()):
        self.schedule = schedule
        self.options = options
        
        # set handle last - there might be custom processing that requires options to already be set
        self.handle = handle  # 'handle' is source/target of schedule in general

    def _write_to_file(self, content, filename):
        with open(filename, 'wb') as fp:
            fp.write(content.strip().encode('UTF-8'))

    def get_handle_mtime(self):
        """ Implement only if schedule handler is able to get mtime directly
        without storage """
        raise NotImplementedError

    def handle_modified_since(self, mtime):
        """ Return boolean to be able to bypass processing """
        # Return False only when able to tell otherwise return True
        
        modified = True
        
        if isinstance(mtime, datetime):
            try:
                handle_mtime = self.get_handle_mtime()
            except NotImplementedError:
                pass

            # we're working with TZ naive dates (but in UTC)
            if handle_mtime: 
                if handle_mtime.tzinfo is not None:
                    handle_mtime = handle_mtime.astimezone(pytz.utc).replace(tzinfo=None)
                
                if handle_mtime <= mtime:
                    modified = False

        return modified

    def get_handle_changelog(self):
        raise NotImplementedError

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
    default_export_ext = 'tjx'
    
    src_tree = None
    provide_changelog = True
    provide_mtime = True
    
    def _get_parsed_tree(self):
        if not self.src_tree:
            self.src_tree = etree.parse(self.handle)
        
        return self.src_tree
    
    def get_handle_changelog(self):
        # import changelog
        changelog = {}
        
        for log in self._get_parsed_tree().xpath('changelog/log'):
            changelog[log.get('rev')] = {
                'date': datetime.strptime(log.get('date'), '%Y/%m/%d'),
                'user': log.get('user'),
                'msg': log.text.strip(),
            }
            
        return changelog

    def get_handle_mtime(self):
        mtime = None
        
        changelog = self.get_handle_changelog()
        
        if changelog:
            mtime = changelog.values()[0]['date']
        
        return mtime

