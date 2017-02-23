class StorageNotCloned(Exception):
    pass


class StorageBase(object):
    handle = None
    opt_args = {}

    def __init__(self, opt_args=dict()):
        self.opt_args = opt_args

    def clone(self, target_dir=None):
        """
        Download repo into target_dir, optionally checkout (cvs terminology)
        content accoding to passed revision or date - this behavior don't
        have to be always implemented due different workflow (i.e. cvs vs. git).
        If they are specified both, revision has precedence.

        Args:
            target_dir: if None, clone to tmp dir

        Returns:
            Path to downloaded local working copy of repository

        """
        # always download to /tmp, if need move to target
        raise NotImplementedError

    def checkout(self, revision=None, datetime=None):
        """
        Get specific version of handle (usualy file) based on revision
        or datetime. If they are specified both, revision has precedence.

        Args:
            revision: checkout specific revision
            datetime: checkout regarding to specific date

        Returns:

        """
        raise NotImplementedError

    def get_local_handle(self, handle):
        """
        Returns path to local (working) 'copy' of handle from storage,
        that don't have to be always local file.
        """
        raise NotImplementedError

    def push(self):
        raise NotImplementedError    
    
    def get_mtime(self, handle):
        raise NotImplementedError

    def modified_since(self, mtime):
        raise NotImplementedError
    
    def get_changelog(self, handle):
        return []

    def build_handle(self, handle):
        raise NotImplementedError


def sync_nfs(local, remote, path=None):
    pass