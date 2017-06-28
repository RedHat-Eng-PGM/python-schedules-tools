import datetime


class AcquireLockException(Exception):
    pass


class StorageBase(object):
    handle = None
    options = {}
    tmp_root = None
    
    provide_changelog = False
    provide_mtime = False

    def __init__(self, handle=None, options=dict()):
        self.handle = handle  # 'handle' is source/target of schedule in general        
        self.options = options

    def get_local_handle(self, revision=None, datetime=None):
        """
        Get specific version of handle (usually file) based on revision
        or datetime. If they are specified both, revision has precedence.

        Args:
            revision: checkout specific revision
            datetime: checkout regarding to specific date

        Returns:

        """
        raise NotImplementedError

    def clean_local_handle(self):
        raise NotImplementedError

    def push(self):
        raise NotImplementedError    
    
    def get_handle_mtime(self):
        raise NotImplementedError

    def handle_modified_since(self, mtime):
        # Return False only when able to tell
        if isinstance(mtime, datetime.datetime):
            try:
                handle_mtime = self.get_handle_mtime()
            except NotImplementedError:
                return True
            if handle_mtime and handle_mtime <= mtime:
                return False

        return True

    def get_handle_changelog(self):
        raise NotImplementedError


def sync_nfs(local, remote, path=None):
    pass
