
class ScheduleStorageBase(object):
    def pull(self, handle, rev=None, date=None):
        pass
    
    def push(self, handle):
        pass    
    
    def get_changelog(self, handle):
        pass
    


def sync_nfs(local, remote, path=None):
    pass