class StorageNotCloned(Exception):
    pass


class ExceptionCheckoutPathExistst(Exception):
    pass


class StorageBase(object):
    handle = None
    opt_args = {}

    def __init__(self, handle=None, opt_args=dict()):
        self.handle = handle  # 'handle' is source/target of schedule in general        
        self.opt_args = opt_args

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

    def push(self):
        raise NotImplementedError    
    
    def get_handle_mtime(self):
        raise NotImplementedError

    def handle_modified_since(self, mtime):
        # Return False only when able to tell
        if isinstance(mtime, datetime):
            handle_mtime = self.get_handle_mtime()
            if handle_mtime and handle_mtime <= mtime:
                return False
        
        return True

    
    def get_handle_changelog(self):
        return []



def sync_nfs(local, remote, path=None):
    pass