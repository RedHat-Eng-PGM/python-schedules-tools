from schedules_tools.storage import StorageBase
import os
import sys
import re
import subprocess
import datetime
import tempfile
import logging

logger = logging.getLogger(__name__)


class StorageHandler_cvs(StorageBase):
    target_dir = None
    cloned = False
    repo_root = None
    repo_name = None
    
    provide_changelog = True

    def __init__(self, handle, opt_args=dict()):
        super(StorageHandler_cvs, self).__init__(handle, opt_args)
        
        self.repo_name = opt_args.pop('cvs_repo_name')
        self.repo_root = opt_args.pop('cvs_root')
        self.opt_args = opt_args

    def _cvs_command(self, cmd, stdout=sys.stdout):
        # -q, make cvs more quiet
        # -z9, maximum compression
        # -d, set CVSROOT
        cmd_str = 'cvs -q -z9 -d {} {}'.format(self.repo_root, cmd)
        p = subprocess.Popen(cmd_str.split(), stdout=stdout,
                             cwd=self.target_dir)
        return p

    def clone(self, target_dir=None):
        if self.cloned:
            logger.debug('Storage has been already cloned. Skipping.')
            return self.target_dir

        if target_dir and not os.path.exists(target_dir):
            os.makedirs(target_dir)
        else:
            target_dir = tempfile.mkdtemp()
        self.target_dir = target_dir

        cmd = 'co {}'.format(self.repo_name)
        p = self._cvs_command(cmd)
        p.communicate()

        assert p.returncode == 0
        self.cloned = True

        return self.target_dir

    def checkout(self, revision=None, datetime=None):
        cmd_revision = ''
        if datetime:
            datetime_str = datetime.strftime('%Y-%m-%d %H:%M')
            cmd_revision = '-D "{}"'.format(datetime_str)
        if revision:
            cmd_revision = '-r "{}"'.format(revision)

        cmd = 'update {cmd_revision} {filename}'.format(
            cmd_revision=cmd_revision, filename=self.handle)
        p = self._cvs_command(cmd)
        p.communicate()
        assert p.returncode == 0

    def get_handle_mtime(self):
        changelog = self.get_changelog(self.handle)
        latest_change = changelog[-1]
        return latest_change['datetime']

    def get_handle_changelog(self):
        changelog = []
        cmd = 'log {}'.format(self.handle)
        p = self._cvs_command(cmd, stdout=subprocess.PIPE)
        stdout, stderr = p.communicate()

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
                self.latest_change = matches[0]

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
                date = datetime.datetime.strptime(matches[0][0],
                                                  '%Y/%m/%d %H:%M:%S')
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
                        'revision': revision,
                        'author': author,
                        'datetime': date,
                        'message': comment
                    }
                    changelog.append(record)
                    state = STATE_REVISION
                    continue
                comment.append(line)
                continue

        # sort records according to date
        return sorted(changelog, key=lambda x: x['datetime'])
