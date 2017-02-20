class ScheduleStorageBase(object):
    opt_args = {}

    def __init__(self, opt_args=dict()):
        self.opt_args = opt_args

    def pull(self, handle=None, rev=None, date=None, target_dir=None):
        ''' Pulls from storage
        
        Args:
            handle: if None - pull all
            rev: if None - pull current
            target_dir: if None, pull to tmp dir
            
        Returns:
            Pulled file/directory
        '''
        # pull always to tmp, if need move to target
        pass
    
    def push(self, handle):
        pass    
    
    def get_changelog(self, handle):
        return []


class Changelog(object):
    revision = None
    author = None
    date = None
    comment = None

    def __init__(self, revision, author, date, comment):
        self.revision = revision
        self.author = author
        self.date = date
        self.comment = comment

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return '{rev}, {date} ({author}): {comment}'.format(
            rev=self.revision,
            date=self.date,
            author=self.author,
            comment=self.comment[:40]
        )


def sync_nfs(local, remote, path=None):
    pass