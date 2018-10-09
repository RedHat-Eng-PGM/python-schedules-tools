import logging
import os
import re
import shutil
import subprocess
import tempfile

import datetime as datetime_mod

from distutils.dir_util import remove_tree, copy_tree

from schedules_tools import SchedulesToolsException
from schedules_tools.storage_handlers import StorageBase

log = logging.getLogger(__name__)


class CvsCommandException(SchedulesToolsException):
    pass


class NotImplementedFeature(SchedulesToolsException):
    pass


class StorageHandler_cvs(StorageBase):
    provide_mtime = True
    provide_changelog = True

    checkout_dir = None  # path to shared local working copy of repository
    repo_root = None  # :pserver:$USER@cvs.myserver.com:/cvs/reporoot
    repo_name = None  # repo

    tmp_root = None  # local tmp handle dir
  
    refresh_validity = 5 # seconds
    _last_refresh_local = None
    block_refresh = False  # allows to skip refresh

    local_handle = None
    
    exclusive_access_option = 'exclusive_access'

    def __init__(self, handle=None, options=dict(), **kwargs):
        self.checkout_dir = options.get('cvs_checkout_path')
        self.checkout_dir_perm = options.get('cvs_checkout_dir_permission',
                                             None)
        self.repo_name = options.get('cvs_repo_name')
        self.repo_root = options.get('cvs_root')    
        self.block_refresh = options.get('cvs_block_refresh', False)  

        super(StorageHandler_cvs, self).__init__(handle, options, **kwargs)

    @property
    def redis_key(self):
        return '_'.join([super(StorageHandler_cvs, self).redis_key,
                         self.repo_root,
                         self.repo_name,
                         self.checkout_dir])

    def _cvs_command(self, cmd,
                     stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE,
                     cwd=None,
                     exclusive=False):
        if not cwd:
            cwd = self.checkout_dir
        # -q, make cvs more quiet
        # -z9, maximum compression
        # -d, set CVSROOT
        cmd_str = 'cvs -q -z9 -d {} {}'.format(self.repo_root, cmd)

        if exclusive:
            self.acquire_shared_lock(msg='command "{}"'.format(cmd_str))

        log.debug('CVS command: {} (cwd={})'.format(cmd_str, cwd))
        p = subprocess.Popen(cmd_str.split(),
                             stdout=stdout,
                             stderr=stderr,
                             cwd=cwd)
        stdout, stderr = p.communicate()
        
        if exclusive:
            self.release_shared_lock()

        if p.returncode != 0:
            msg = str({'stdout': stdout, 'stderr': stderr, 'cmd': cmd_str})
            raise CvsCommandException(msg, source=self)
        
        return stdout, stderr

    @staticmethod
    def _wipe_out_dir(target_dir):
        if os.path.exists(target_dir):
            log.debug('Wipping out {}'.format(target_dir))
            remove_tree(target_dir)

    def _is_valid_cvs_dir(self, path):
        """
        Verifies that given (local) path comes from CVS local working copy
         - contains CVS directory
         - <path>/CVS/Root ends like: '@cvs.myserver.com:/cvs/reporoot'
         - <path>/CVS/Repository 'repo/' - path to tracked directory

        Args:
            path: local path of versioned directory (/tmp/cvsXZY/repo/schedule)

        Returns:
            True, if the path come from the already checked out repo
        """
        def get_subpath(*subpath):
            return os.path.join(path, *subpath)

        def cvs_root_parser(string):
            # :gserver:$USER@cvs.myserver.com:/cvs/reporoot or local /cvs/root
            chunks = string.split(':')
            if len(chunks) == 1:
                server_url = ''
                server_path = chunks[0]
            else:
                server_url = chunks[2].split('@')[1]
                server_path = chunks[3]
            return server_url, server_path

        if not os.path.exists(path):
            return False

        # CVS has to be a directory
        if not os.path.isdir(get_subpath('CVS')):
            return False

        # verify CVS module name (repo_name)
        with open(get_subpath('CVS', 'Repository')) as fd:
            line = fd.readline().strip()
            if not line.startswith(self.repo_name):
                return False

        # verify CVS Root
        with open(get_subpath('CVS', 'Root')) as fd:
            line = fd.readline().strip()
            if cvs_root_parser(line) != cvs_root_parser(self.repo_root):
                return False

        return True

    def get_local_shared_path(self, path):
        """
        Returns path to file that belongs local working copy of repository

        Args:
            path: relative path in repo (repo/schedule)

        Returns:
            Real local path to given file within repo (/tmp/tmpXYZ/repo/schedule)
        """
        ret = os.path.join(self.checkout_dir, self.repo_name, path)
        return os.path.realpath(ret)

    def refresh_local(self, force=False):
        """
        Check if local copy exists (not just path but also CVS content) and
        decide if checkout is needed or not
        If empty:
            do a cvs checkout to mkdtmp dir and then copy to local path
        If exists:
            do a cvs update - handle conflicts,...
        """
        cvs_content_root_dir = os.path.join(self.checkout_dir, self.repo_name)

        if not self._is_valid_cvs_dir(cvs_content_root_dir):
            self._cvs_checkout()

        elif not self.block_refresh:
            # use redis key if possible to share value across workers
            datetime_format = '%Y-%m-%d %H:%M:%S'
            last_refresh_local_time_key = self.redis_key + '_last_refresh_local'
            last_refresh_expired = True  # init

            if self.redis:
                last_refresh_time = self.redis.get(last_refresh_local_time_key)
            else:
                last_refresh_time = self._last_refresh_local

            if last_refresh_time:
                last_refresh_time = datetime_mod.datetime.strptime(last_refresh_time,
                                                                   datetime_format)
                last_refresh_expired = (last_refresh_time <
                                        datetime_mod.datetime.now() - datetime_mod.timedelta(seconds=self.refresh_validity))

            if force or last_refresh_expired:
                self._update_shared_repo()

                last_refresh_time = datetime_mod.datetime.now().strftime(datetime_format)
                self._last_refresh_local = last_refresh_time

                if self.redis:
                    self.redis.set(last_refresh_local_time_key, last_refresh_time)


    def _copy_subtree_to_tmp(self, processed_path):
        """
        Create an independent copy of schedule (from main-cvs-checkout),
        located in /tmp and

        Args:
            processed_path: relative subtree path of shared checkout dir

        Returns:
            Path to processed_path copied directory  in /tmp
        """
        src = os.path.join(self.checkout_dir, self.repo_name, processed_path)
        
        dst_tmp_dir = tempfile.mkdtemp(prefix='sch_')
        dst = os.path.join(dst_tmp_dir, processed_path)
        
        # lock cvs so nothing changes during copy
        self.acquire_shared_lock(msg='copying subtree from shared cvs copy')
        copy_tree(src, dst)
        self.release_shared_lock()

        return dst_tmp_dir
    
    def _process_path(self):
        """
        Get handle and figure out, which directory subtree needs to be check
        out
        Example: schedule/schedule-1-0.tjp -> schedule

        Returns:
            Path to schedule, that handle is part of ('schedule')
        """
        return os.path.dirname(self.handle)

    def get_local_handle(self, enforce=False, revision=None, datetime=None):
        """
        Facilitate update/clone of shared working copy of repository,

        Args:
            revision:
            datetime:

        Returns:
            Tuple (path_to_handle, path_to_tmp_dir)

        """
        if not self.local_handle or enforce:
            # Checkout exact revision/datetime if defined
            if revision or datetime:
                raise NotImplementedFeature(
                    'Checking out specific revision is not currently '
                    'implemented.')

            self.refresh_local()  # refresh shared local tree
            subtree_rel_path = self._process_path()
            self.tmp_root = self._copy_subtree_to_tmp(subtree_rel_path)

            self.local_handle = os.path.join(self.tmp_root, self.handle)
            log.debug('Creating local handle {}'.format(self.local_handle))

        return self.local_handle

    def clean_local_handle(self):
        if self.local_handle:
            log.debug('Cleaning local handle {}'.format(self.local_handle))
            
            remove_tree(self.tmp_root)
            self.local_handle = None

    def _cvs_checkout(self, force=False):
        """
        Clones the repo into:
            1) cvs_checkout_path optional param
            2) made temp directory

        Set self.checkout_dir to new, proper path accordingly.
        """
        verify_existing_dif = True

        if not self.checkout_dir:
            verify_existing_dif = False
            self.checkout_dir = tempfile.mkdtemp(prefix='sch_repo_')

        log.debug('Using {} as checkout dir'.format(self.checkout_dir))

        if force:
            verify_existing_dif = False

        local_repo_path = self.get_local_shared_path(self.repo_name)
        if verify_existing_dif and self._is_valid_cvs_dir(local_repo_path):
            return self.checkout_dir

        temp_checkout_dir = tempfile.mkdtemp(prefix='sch_tmp_repo_')
        cmd = 'co {}'.format(self.repo_name)

        self._cvs_command(cmd, cwd=temp_checkout_dir, exclusive=True)

        # Finally move whole content into required destination. Due behavior of
        # 'move', the destination don't have to exists. That's why it can't be
        # done as atomic operation.
        # 'atomic' part start
        self._wipe_out_dir(self.checkout_dir)
        shutil.move(temp_checkout_dir, self.checkout_dir)
        # 'atomic' part end

        if self.checkout_dir_perm:
            os.chmod(self.checkout_dir, self.checkout_dir_perm)

        return self.checkout_dir

    def _cvs_update(self, filename='', revision=None, datetime_rev=None):
        """
        Run 'cvs update' with given filename or if it's not specified whole
        local working copy of repository and specification of revision
        to get, if it's specified.

        Args:
            filename: relative path (repo/schedule/schedule-1-0)
            revision: Optional, pick specific revision by revision number
            datetime_rev: Optional, pick specific revision by date

        Returns:
            stdout/err of 'cvs' command
        """
        cmd_revision = ''
        cvs_params = ''
        # -d = retrieve also new directories
        # -P = prune empty directories        
        cmd_params = '-dP'

        if revision and datetime_rev:
            raise CvsCommandException('Revision specification by number and '
                                      'date are disjunctive. Pick just one.',
                                      source=self)

        if datetime_rev:
            datetime_str = datetime_rev.strftime('%Y-%m-%d %H:%M')
            cmd_revision = '-D "{}"'.format(datetime_str)
        if revision:
            cmd_revision = '-r "{}"'.format(revision)

        cmd = '{cvs_params} update {cmd_params} {cmd_revision} {filename}'.format(
            cvs_params=cvs_params,
            cmd_params=cmd_params,
            cmd_revision=cmd_revision, filename=filename).strip()
        stdout, stderr = self._cvs_command(cmd, exclusive=True)
        return stdout, stderr

    def _update_shared_repo(self):
        """
        Wraps 'cvs update' and in case of problems, fix the shared working copy
        of the repo (remove the dir, checkout it again), or as a last chance,
        do complete checkout of the repository from scratch.
        """
        try:
            stdout, stderr = self._cvs_update()

            # Are there any directories with troubles? Remove them (afterwards).
            to_cleanup = self._parse_cvs_update_output(stdout)

            # There are no problems - nothing to do, leaving.
            if not to_cleanup:
                return

            for path in to_cleanup:
                self._clean_checkout_directory(path)

            # This step is just for sure - shouldn't occur usually
            stdout, stderr = self._cvs_update()
            to_cleanup = self._parse_cvs_update_output(stdout)
            if to_cleanup:
                # Something went wrong by update, do complete fresh checkout
                self._cvs_checkout(force=True)
        except CvsCommandException as e:
            log.exception(e)
            self._cvs_checkout(force=True)

    @staticmethod
    def _parse_cvs_update_output(cvsoutput):
        """
        Parse line by line from given argument and returns list of paths, that's
        somehow corrupted and have to be updated/checkouted from scratch.

        Args:
            cvsoutput: string with (usually) multiple lines, stdout of
                       'cvs update' command

        Returns:
            list of paths, that's corrupted

        """
        re_flags = re.compile('^(\S)\s+(\S+)')
        to_cleanup = set()

        for line in cvsoutput.splitlines():
            match = re.findall(re_flags, line)
            if not match:
                continue
            flag, filename = match[0]
            path = os.path.dirname(filename)
            # Conflict, Added, Modified locally, ? not versioned yet
            if flag in ('C', 'A', 'M', '?'):
                if path != '':
                    to_cleanup.add(path)
            # Updated, Patched
            elif flag in ('U', 'P'):
                # it's valid state - there exists remote changes,
                # local working copy doesn't have any external changes
                pass
            else:
                log.debug('Unknown CVS status flag: ' + flag)
                # Don't know what it means, so clean it to be sure
                if path != '':
                    to_cleanup.add(path)
        return to_cleanup

    def _clean_checkout_directory(self, directory):
        log.debug('Wipe out checkout directory {}'.format(directory))
        rm_dir = os.path.join(self.checkout_dir, directory)
        if os.path.exists(rm_dir):
            # lock cvs so nothing changes during cleanup
            self.acquire_shared_lock(msg='cleaning shared cvs copy')            
            remove_tree(rm_dir)
            self.release_shared_lock()

    def get_handle_mtime(self):
        self.refresh_local()

        local_handle = self.get_local_shared_path(self.handle)
        mtime_timestamp = os.path.getmtime(local_handle)
        return datetime_mod.datetime.fromtimestamp(mtime_timestamp).replace(microsecond=0)

    def get_handle_changelog(self):
        self.refresh_local()

        changelog = {}
        cmd = 'log {}'.format(os.path.join(self.repo_name, self.handle))
        stdout, stderr = self._cvs_command(cmd)

        STATE_HEAD = 'head'
        STATE_REVISION = 'revision'
        STATE_DATE_AUTHOR = 'dateauthor'
        STATE_COMMENT = 'comment'

        state = STATE_HEAD

        revision = None
        author = None
        date = None
        comment = []
        re_date_author = re.compile('date:\s*([^;]+);\s+author:\s*([^;]+);')
        re_head = re.compile('head:\s+(.+)')
        re_revision = re.compile('revision\s+(.+)')
        re_branches = re.compile('branches:\s+(.+);')
        log_separator = '----------------------------'
        log_end_separator = '============================================================================='

        for line in stdout.splitlines():
            if state == STATE_HEAD:
                matches = re_head.findall(line)
                if not matches:
                    continue

                state = STATE_REVISION
                continue
            elif state == STATE_REVISION:
                # new record, clean all previous values
                matches = re_revision.findall(line)
                if not matches:
                    continue
                revision = matches[0]
                author = None
                date = None
                comment = []

                state = STATE_DATE_AUTHOR
                continue
            elif state == STATE_DATE_AUTHOR:
                matches = re_date_author.findall(line)
                date = datetime_mod.datetime.strptime(
                    matches[0][0], '%Y/%m/%d %H:%M:%S')
                author = matches[0][1]
                comment = []

                state = STATE_COMMENT
                continue
            elif state == STATE_COMMENT:
                br = re_branches.match(line)
                if not comment and br:
                    continue
                if line == log_separator or line == log_end_separator:
                    # store whole log
                    comment = '\n'.join(comment)
                    record = {
                        'user': author,
                        'date': date,
                        'msg': comment
                     }
                    changelog[revision] = record
                    state = STATE_REVISION
                    continue
                comment.append(line)
                continue

        return changelog
