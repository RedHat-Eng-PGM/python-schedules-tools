class ScheduleStorageBase(object):
    handle = None
    
    opt_args = {}

    def __init__(self, opt_args=dict()):
        self.opt_args = opt_args

    def pull(self, rev=None, datetime=None, target_dir=None):
        ''' Pulls from storage
        
        Args:
            rev: if None - pull current
            datetime: if no rev - pull content state from specified datetime
            target_dir: if None, pull to tmp dir
            
        Returns:
            Pulled file/directory
        '''
        # pull always to tmp, if need move to target
        raise NotImplementedError
    
    def push(self):
        raise NotImplementedError    
    
    def get_mtime(self):
        raise NotImplementedError

    def modified_since(self, mtime):
        raise NotImplementedError
    
    def get_changelog(self):
        return []


def sync_nfs(local, remote, path=None):
    pass