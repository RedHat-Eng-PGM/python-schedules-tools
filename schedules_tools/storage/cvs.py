from schedules_tools.storage import ScheduleStorageBase, Changelog
import os
import sys
import re
import subprocess
import datetime
import tempfile
import logging

logger = logging.getLogger(__name__)


class ScheduleStorage_cvs(ScheduleStorageBase):
    target_dir = None
    envvars = dict()
    cloned = False
    repo_url = None
    repo_name = None

    def __init__(self, opt_args=dict()):
        self.repo_name = opt_args.pop('cvs_repo_name')
        self.opt_args = opt_args
        self.envvars = os.environ
        self.envvars['CVSROOT'] = opt_args.pop('cvs_root')

    def _clone(self, target_dir=None):
        if self.cloned:
            logger.debug('Storage has been already cloned. Skipping.')
            return
        if not target_dir:
            target_dir = '/tmp'
        self.target_dir = target_dir
        tempfile.mkdtemp()
        os.makedirs(self.target_dir)

        cmd = 'cvs co {}'.format(self.repo_name)
        p = subprocess.Popen(cmd.split(), env=self.envvars, stdout=sys.stdout,
                             cwd=self.target_dir)
        p.communicate()
        assert p.returncode == 0
        self.cloned = True

    def _checkout(self, revision=None, filename=None):
        if not filename:
            filename = ''
        cmd = 'cvs update -r{revision} {filename}'.format(
            revision=revision, filename=filename)
        p = subprocess.Popen(cmd.split(), env=self.envvars, stdout=sys.stdout,
                             cwd=self.target_dir)
        p.communicate()
        assert p.returncode == 0

    def pull(self, handle=None, rev=None, date=None, target_dir=None):
        """ Pulls from storage

        Args:
            handle: if None - pull all
            rev: if None - pull current
            date:
            target_dir: if None, pull to tmp dir

        Returns:
            Pulled file/directory
        """
        self._clone(target_dir)
        self._checkout(revision=rev,)

    def parse_changelog(self, filename):
        changelog = []
        cmd = 'cvs log {}'.format(filename)
        p = subprocess.Popen(cmd.split(), env=self.envvars, cwd=self.target_dir,
                             stdout=subprocess.PIPE)
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
                if line == log_separator:
                    # store whole log
                    comment = '\n'.join(comment)
                    record = Changelog(revision, author, date, comment)
                    changelog.append(record)
                    state = STATE_REVISION
                    continue
                comment.append(line)
                continue

        # sort records according to date
        return sorted(changelog, key=lambda x: x.date)
