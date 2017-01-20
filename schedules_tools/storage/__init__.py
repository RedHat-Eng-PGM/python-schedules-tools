
class ScheduleStorageBase(object):
    def pull(self, handle=None, rev=None, date=None, tgt_dir=None):
        ''' Pulls from storage
        
        Args:
            handle: if None - pull all
            rev: if None - pull current
            tgt_dir: if None, pull to tmp dir
            
        Returns:
            Pulled file/directory
        '''
        # pull always to tmp, if need move to target
        pass
    
    def push(self, handle):
        pass    
    
    def get_changelog(self, handle):
        return []
    


def sync_nfs(local, remote, path=None):
    pass