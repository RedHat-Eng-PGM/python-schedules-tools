import datetime
import logging

from schedules_tools import SchedulesToolsException


log = logging.getLogger(__name__)

try:
    import redis
    redis_available = True
except ImportError:
    log.info('Redis unavailable - will not use exclusive access to storage')
    redis_available = False


class AcquireLockException(SchedulesToolsException):
    pass


class StorageBase(object):
    handle = None
    options = {}
    tmp_root = None
    
    provide_changelog = False
    provide_mtime = False
    
    exclusive_access = False
    exclusive_access_option = 'exclusive_access'
    redis = None    
    
    _shared_lock = None  # shared copy lock
    lock_acquired = None
    lock_timeout = 120
    lock_sleep = 0.5  # seconds
    lock_max_workers = 10  # max number of workers waiting
    

    def __init__(self, handle=None, options=dict()):
        self.handle = handle  # 'handle' is source/target of schedule in general        
        self.options = options
        
        self.exclusive_access = redis_available and options.get(self.exclusive_access_option, 
                                                                self.exclusive_access)

        if self.exclusive_access:
            redis_url = options.get('redis_url', '')
            
            if redis_url:
                self.redis = redis.StrictRedis.from_url(redis_url)
            else:
                self.redis = redis.StrictRedis()

            self._shared_lock = self.redis.lock(
                                name=self.redis_key, 
                                timeout=self.lock_timeout - 10,  # max life time for lock 
                                sleep=self.lock_sleep, 
                                blocking_timeout=self.lock_timeout * self.lock_max_workers
                            )         

    @property
    def redis_key(self):
        return '_'.join(['schedules_tools', self.__class__.__name__])
        

    def acquire_shared_lock(self, msg=''):
        if self.exclusive_access:
            log.debug('Waiting for {} shared lock..'.format(self.__class__.__name__))             
            self.lock_acquired = self._shared_lock.acquire()          

            if not self.lock_acquired:
                raise AcquireLockException(
                    'Unable to acquire lock {}'.format(msg),
                    source=self
                )
            else:
                log.debug('{} shared lock ACQUIRED'.format(self.__class__.__name__))
        
    def release_shared_lock(self):
        if self.lock_acquired:
            self._shared_lock.release()
            log.debug('{} shared lock RELEASED'.format(self.__class__.__name__))  


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
