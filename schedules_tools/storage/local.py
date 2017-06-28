from schedules_tools import storage
import os
from datetime import datetime


class StorageHandler_local(storage.StorageBase):
    provide_mtime = True

    def get_local_handle(self, revision=None, datetime=None):
        return self.handle

    def clean_local_handle(self):
        pass

    def get_handle_mtime(self, path=None):
        mtime_timestamp = os.path.getmtime(self.handle)

        return datetime.fromtimestamp(mtime_timestamp).replace(microsecond=0)

    def _copy_subtree_to_tmp(self):
        """
        Create an independent copy of product (from main-cvs-checkout),
        located in /tmp and

        Returns:
            Path to process_path copied directory  in /tmp
        """
        dst_tmp_dir = tempfile.mkdtemp(prefix='sch_')
        shutil.copy2(self.handle, dst_tmp_dir)

        return dst_tmp_dir
