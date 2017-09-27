from schedules_tools import storage_handlers
import os
from datetime import datetime


class StorageHandler_local(storage_handlers.StorageBase):
    provide_mtime = True

    def get_local_handle(self, revision=None, datetime=None):
        return self.handle

    def clean_local_handle(self):
        pass

    def get_handle_mtime(self, path=None):
        mtime_timestamp = os.path.getmtime(self.handle)

        return datetime.fromtimestamp(mtime_timestamp).replace(microsecond=0)
