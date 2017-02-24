from datetime import datetime
import logging
import time
import os

logger = logging.getLogger(__name__)

# schedules are in US TZ
os.environ['TZ'] = 'America/New_York'
time.tzset()


# Handle implementation must be in format ScheduleHandler_format
# where 'format' is used as a uniq label for the format and
# 'ScheduleHandler' can be whatever.
class ScheduleHandlerBase(object):
    handle = None
    schedule = None
    
    # optional source storage handler instance to get changelog/mtime from if applicable
    src_storage_handler = None

    # This flag indicate ability to export internal intermediate structure
    # (Schedule) into format of implementation. It's read by ScheduleConverter
    # during autodiscovery and used to provide actual help message in CLI
    provide_export = False
    
    opt_args = {}

    def __init__(self, handle=None, schedule=None, src_storage_handler=None, 
                 opt_args=dict()):
        self.handle = handle  # 'handle' is source/target of schedule in general
        self.schedule = schedule
        self.src_storage_handler = src_storage_handler
        self.opt_args = opt_args

    def _write_to_file(self, content, file):
        with open(file, 'wb') as fp:
            fp.write(content.strip().encode('UTF-8'))

    def get_handle_mtime(self):
        raise NotImplementedError
    
    def handle_modified_since(self, mtime):
        raise NotImplementedError
    
    def get_handle_changelog(self):
        return []
    
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

    def _get_mtime_from_handle_file(self):
        mtime = os.path.getmtime(self.handle)
        return datetime.fromtimestamp(mtime)


class TJXChangelogMixin(object):
    def parse_tjx_changelog(self, tree):
        # import changelog
        for log in tree.xpath('changelog/log'):
            self.schedule.changelog[log.get('rev')] = {
                'date': datetime.strptime(log.get('date'), '%Y/%m/%d'),
                'user': log.get('user'),
                'msg': log.text.strip(),
            }
