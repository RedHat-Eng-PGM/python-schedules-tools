import datetime
import logging
import time
import os

logger = logging.getLogger('pp.core')

# schedules are in US TZ
os.environ['TZ'] = 'America/New_York'
time.tzset()


if hasattr(datetime.datetime, 'strptime'):
    # python 2.6
    strptime = datetime.datetime.strptime
else:
    # python 2.4 equivalent
    import time
    strptime = lambda date_string, dFormat: datetime.datetime(*(time.strptime(date_string, dFormat)[0:6]))


# Handle implementation must be in format ScheduleHandler_format
# where 'format' is used as a uniq label for the format and
# 'ScheduleHandler' can be whatever.
class ScheduleHandlerBase(object):
    schedule = None
    
    # source storage to get changelog from if applicable
    src_storage = None

    # This flag indicate ability to export internal intermediate structure
    # (Schedule) into format of implementation. It's read by ScheduleConverter
    # during autodiscovery and used to provide actual help message in CLI
    provide_export = False

    def __init__(self, schedule=None, src_storage=None):
        self.schedule = schedule
        self.src_storage = src_storage

    # handle - file/link/smartsheet id
    def import_schedule(self, handle):
        pass

    def export_schedule(self, output):
        pass   
    
    def build_schedule(self, handle):
        pass 

    @staticmethod
    def is_valid_source(handle):
        """Method returns True, if the specific handler is able to work with
        given handle"""
        pass

    def extract_backup(self, handle):
        """Prepare files which need a backup in case of external source"""
        return []


class TJXChangelog(object):
    def parse_changelog(self, tree):
        # import changelog
        for log in tree.xpath('changelog/log'):
            self.schedule.changelog[log.get('rev')] = {
                'date': strptime(log.get('date'), '%Y/%m/%d'),
                'user': log.get('user'),
                'msg': log.text.strip(),
            }
