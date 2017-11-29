import datetime
import mock
import os
import pytest

from schedules_tools.storage_handlers import cvs as cvs_mod
from schedules_tools import storage_handlers
from schedules_tools.tests import jsondate

BASE_DIR = os.path.dirname(os.path.realpath(__file__))


class BaseCvsTest(object):
    handler_class = cvs_mod

    @classmethod
    def _make_reference_obj(cls, handle=None, checkout_dir=None, options=dict()):
        options = {
            'cvs_repo_name': 'repo',
            'cvs_root': ':gserver:someuser@cvs.myserver.com:/cvs/repo',
            'cvs_checkout_path': checkout_dir,
        }
        reference = cls.handler_class.StorageHandler_cvs(handle, options=options)
        return reference


class BaseCvsWithDefaultHandler(BaseCvsTest):
    reference_obj = None
    handle = 'program/rhel/rhel-7-0-0/rhel-7-0-0.tjp'
    checkout_dir = '/tmp/mycheckoutdir'

    @pytest.fixture(autouse=True)
    def setUp(self):
        self.reference_obj = self._make_reference_obj(self.handle,
                                                      self.checkout_dir)


class TestCvsCustomRepo(BaseCvsTest):
    def test_get_local_shared_path(self):
        checkout_dir = '/tmp/aaa'
        reference = self._make_reference_obj(checkout_dir=checkout_dir)
        path = 'program/release'

        ret = reference.get_local_shared_path(path)

        assert ret == '/tmp/aaa/repo/program/release'

    @mock.patch('schedules_tools.storage_handlers.cvs.os')
    def test_is_valid_cvs_dir_root_negative(self, mock_os):
        options = {
            'cvs_repo_name': 'program',
            'cvs_root': ':gserver:someuser@cvs.myserver.com:/cvs/reporoot'
        }
        path = 'program/product/release-1-2-3'

        reference = cvs_mod.StorageHandler_cvs(options=options)

        mock_fileopen = mock.mock_open(read_data=path)
        mock_cvs_repo = mock_fileopen
        cvs_root = ':gserver:otheruser@cvs.myserver.com:/cvs/reporoot/abc/def/h'
        mock_cvs_root = mock.mock_open(read_data=cvs_root)
        mock_fileopen.side_effect = [
            mock_cvs_repo.return_value,
            mock_cvs_root.return_value]

        mock_os.path.isdir.return_value = True
        with mock.patch('__builtin__.open', mock_fileopen):
            assert not reference._is_valid_cvs_dir(path)

    @mock.patch.object(cvs_mod.StorageHandler_cvs, 'refresh_local')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, 'get_local_shared_path')
    @mock.patch('schedules_tools.storage_handlers.cvs.os.path.getmtime')
    @mock.patch('schedules_tools.storage_handlers.cvs.os')
    def test_get_handle_mtime(self,
                              mock_os,
                              mock_getmtime,
                              mock_get_local_shared_path,
                              mock_refresh_local):
        handle = 'program/product/release/release.tjp'

        # 1477535432.123 == datetime.datetime(2016, 10, 27, 4, 30, 32, 123000)
        referece_ret = 1477535432.123
        mock_getmtime.return_value = referece_ret

        reference = self._make_reference_obj(handle=handle)

        ret = reference.get_handle_mtime()

        mock_refresh_local.assert_called()
        assert ret == datetime.datetime(2016, 10, 27, 4, 30, 32)
        mock_get_local_shared_path.assert_called_with(handle)

    def test_process_path(self):
        handle = 'program/fedora/f-25/f-25.xml'
        reference = self._make_reference_obj(handle=handle)
        assert reference._process_path() == 'program/fedora/f-25'


class TestCvs(BaseCvsWithDefaultHandler):
    @mock.patch('schedules_tools.storage_handlers.cvs.subprocess.Popen')
    def test_cvs_command(self, mock_popen):
        cmd = 'update program/rhel'

        mock_communicate = mock.Mock()
        mock_communicate.communicate.return_value = ('std-out', 'std-err')
        mock_popen.return_value = mock_communicate
        type(mock_communicate).returncode = mock.PropertyMock(return_value=0)

        return_value = self.reference_obj._cvs_command(cmd)
        assert return_value == ('std-out', 'std-err')
        mock_popen.assert_called()

    @mock.patch('schedules_tools.storage_handlers.cvs.subprocess.Popen')
    def test_cvs_command_nonzero_exit_code(self, mock_popen):
        cmd = 'update program/rhel'

        mock_communicate = mock.Mock()
        mock_communicate.communicate.return_value = ('std-out', 'std-err')
        mock_popen.return_value = mock_communicate
        type(mock_communicate).returncode = mock.PropertyMock(return_value=1)

        with pytest.raises(cvs_mod.CvsCommandException):
            self.reference_obj._cvs_command(cmd)
        mock_popen.assert_called()

    @mock.patch('schedules_tools.storage_handlers.cvs.remove_tree')
    @mock.patch('schedules_tools.storage_handlers.cvs.os')
    def test_wipeout_dir(self, mock_os, mock_remove_tree):
        path = 'somefile'
        mock_os.path.exists.return_value = True

        cvs_mod.StorageHandler_cvs._wipe_out_dir(path)

        mock_os.path.exists.assert_called_with(path)
        mock_remove_tree.assert_called_with(path)

    @mock.patch('schedules_tools.storage_handlers.cvs.remove_tree')
    @mock.patch('schedules_tools.storage_handlers.cvs.os')
    def test_wipeout_dir_not_exists(self, mock_os, mock_remove_tree):
        path = 'somefile'
        mock_os.path.exists.return_value = False

        cvs_mod.StorageHandler_cvs._wipe_out_dir(path)

        mock_os.path.exists.assert_called_with(path)
        mock_remove_tree.assert_not_called()

    @mock.patch('schedules_tools.storage_handlers.cvs.os')
    def test_is_valid_cvs_dir(self, mock_os):
        path = 'repo/product/release-1-2-3'

        mock_fileopen = mock.mock_open(read_data=path)
        mock_cvs_repo = mock_fileopen
        cvs_root = ':gsrv:test@cvs.myserver.com:/cvs/repo'
        mock_cvs_root = mock.mock_open(read_data=cvs_root)
        mock_fileopen.side_effect = [
            mock_cvs_repo.return_value,
            mock_cvs_root.return_value]

        mock_os.path.exists.return_value = True
        mock_os.path.isdir.return_value = True
        with mock.patch('__builtin__.open', mock_fileopen):
            assert self.reference_obj._is_valid_cvs_dir(path)

    @mock.patch('schedules_tools.storage_handlers.cvs.os.path.exists')
    @mock.patch('schedules_tools.storage_handlers.cvs.os.path.isdir')
    def test_is_valid_cvs_dir_CVSdir_negative(self, mock_isdir, mock_exists):
        path = 'program/aa/bbb'
        mock_isdir.return_value = False
        mock_exists.return_value = True

        assert not self.reference_obj._is_valid_cvs_dir(path)
        mock_isdir.assert_called_with('program/aa/bbb/CVS')

    @mock.patch('schedules_tools.storage_handlers.cvs.os.path.exists')
    def test_is_valid_cvs_dir_not_exists_negative(self, mock_exists):
        path = 'program/aa/bbb'
        mock_exists.return_value = False

        assert not self.reference_obj._is_valid_cvs_dir(path)
        mock_exists.assert_called_with('program/aa/bbb')

    @mock.patch('schedules_tools.storage_handlers.cvs.os.path.isdir')
    def test_is_valid_cvs_dir_repository_negative(self, mock_isdir):
        path = 'program/aa/bbb'
        mock_isdir.return_value = True
        mock_fileopen = mock.mock_open(read_data='asdf')

        with mock.patch('__builtin__.open', mock_fileopen):
            assert not self.reference_obj._is_valid_cvs_dir(path)

    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_checkout')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_update_shared_repo')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_is_valid_cvs_dir')
    @mock.patch('schedules_tools.storage_handlers.cvs.os')
    def test_refresh_local(self,
                           mock_os,
                           mock__is_valid_cvs_dir,
                           mock__update_shared_repo,
                           mock__cvs_checkout):
        mock_os.path.exists.return_value = True
        mock__is_valid_cvs_dir.return_value = True

        self.reference_obj.refresh_local()

        mock__update_shared_repo.assert_called()
        mock__cvs_checkout.assert_not_called()

    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_checkout')
    @mock.patch('schedules_tools.storage_handlers.cvs.os')
    def test_refresh_local_missing_shared_dir(
            self,
            mock_os,
            mock__cvs_checkout):
        mock_os.path.exists.return_value = False

        self.reference_obj.refresh_local()

        mock__cvs_checkout.assert_called()

    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_checkout')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_is_valid_cvs_dir')
    @mock.patch('schedules_tools.storage_handlers.cvs.os')
    def test_refresh_local_invalid_shared_dir(
            self,
            mock_os,
            mock__is_valid_cvs_dir,
            mock__cvs_checkout):
        mock_os.path.exists.return_value = True
        mock__is_valid_cvs_dir.return_value = False

        self.reference_obj.refresh_local()

        mock__cvs_checkout.assert_called()

    @mock.patch('tempfile.mkdtemp')
    @mock.patch('schedules_tools.storage_handlers.cvs.copy_tree')
    def test_copy_subtree_to_tmp(self, mock_copy_tree, mock_mkdtemp):
        process_path = 'rhel'
        mock_mkdtemp.return_value = '/tmp/asdf'

        return_value = self.reference_obj._copy_subtree_to_tmp(process_path)

        assert return_value == '/tmp/asdf'
        mock_copy_tree.assert_called_with('/tmp/mycheckoutdir/repo/rhel',
                                          '/tmp/asdf/rhel')

    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_copy_subtree_to_tmp')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, 'refresh_local')
    def test_get_local_handle(self,
                              mock_refresh_local,
                              mock_copy_subtree_to_tmp):
        mock_copy_subtree_to_tmp.return_value = '/tmp/tmpaaa'

        return_value = self.reference_obj.get_local_handle()
        return_ref = '/tmp/tmpaaa/program/rhel/rhel-7-0-0/rhel-7-0-0.tjp'
        assert return_value == return_ref
        assert self.reference_obj.tmp_root == '/tmp/tmpaaa'
        mock_refresh_local.assert_called()

    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_copy_subtree_to_tmp')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, 'refresh_local')
    def test_get_local_handle_multiple_times(self,
                                             mock_refresh_local,
                                             mock_copy_subtree_to_tmp):
        #mock_copy_subtree_to_tmp.return_value = '/tmp/tmpaaa'
        mock_copy_subtree_to_tmp.side_effect = ['/tmp/tmpaaa', '/tmp/tmpbbb', '/tmp/tmpccc']

        return_value = self.reference_obj.get_local_handle()
        return_ref = '/tmp/tmpaaa/program/rhel/rhel-7-0-0/rhel-7-0-0.tjp'
        assert return_value == return_ref
        assert self.reference_obj.tmp_root == '/tmp/tmpaaa'
        mock_refresh_local.assert_called()

        return_value = self.reference_obj.get_local_handle()
        assert return_value == return_ref
        assert self.reference_obj.tmp_root == '/tmp/tmpaaa'
        assert mock_refresh_local.call_count == 1

    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_copy_subtree_to_tmp')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, 'refresh_local')
    @mock.patch('schedules_tools.storage_handlers.cvs.remove_tree')
    def test_clean_local_handle(self,
                                mock_remove_tree,
                                mock_refresh_local,
                                mock_copy_subtree_to_tmp):
        self.reference_obj.get_local_handle()
        self.reference_obj.clean_local_handle()
        mock_remove_tree.assert_called()

        self.reference_obj.clean_local_handle()
        self.reference_obj.clean_local_handle()
        self.reference_obj.clean_local_handle()
        self.reference_obj.clean_local_handle()
        assert mock_remove_tree.call_count == 1

    def test_get_local_handle_get_specific_revision_by_rev(self):
        rev_number = '1.0'
        with pytest.raises(cvs_mod.NotImplementedFeature):
            self.reference_obj.get_local_handle(revision=rev_number)

    def test_get_local_handle_get_specific_revision_by_date(self):
        rev_date = datetime.datetime(2020, 3, 25)
        with pytest.raises(cvs_mod.NotImplementedFeature):
            self.reference_obj.get_local_handle(datetime=rev_date)

    def test_get_local_handle_get_specific_revision_by_rev_and_date(self):
        rev_number = '1.0'
        rev_date = datetime.datetime(2020, 3, 25)
        with pytest.raises(cvs_mod.NotImplementedFeature):
            self.reference_obj.get_local_handle(revision=rev_number,
                                                datetime=rev_date)

    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_command')
    def test_cvs_update(self, mock_cvs_command):
        mock_cvs_command.return_value = ('std-out', 'std-err')

        assert self.reference_obj._cvs_update() == ('std-out', 'std-err')
        mock_cvs_command.assert_called_with('update -dP', exclusive=True)

    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_command')
    def test_cvs_update_revdate(self, mock_cvs_command):
        mock_cvs_command.return_value = ('std-out', 'std-err')

        revision = datetime.date(2011, 9, 25)
        filename = 'myfile'
        output = self.reference_obj._cvs_update(filename, datetime_rev=revision)
        assert output == ('std-out', 'std-err')
        mock_cvs_command.assert_called_with(
            'update -dP -D "2011-09-25 00:00" myfile', exclusive=True)

    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_command')
    def test_cvs_update_revnumber(self, mock_cvs_command):
        mock_cvs_command.return_value = ('std-out', 'std-err')

        revision = '1.27'
        filename = 'myfile'
        output = self.reference_obj._cvs_update(filename, revision=revision)
        assert output == ('std-out', 'std-err')
        mock_cvs_command.assert_called_with(
            'update -dP -r "1.27" myfile', exclusive=True)

    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_command')
    def test_cvs_update_revnumber_revdate(self, mock_cvs_command):
        mock_process = mock.Mock()
        mock_process.communicate.return_value = ('std-out', 'std-err')
        type(mock_process).returncode = mock.PropertyMock(return_value=0)
        mock_cvs_command.return_value = mock_process

        revision = '1.2.3'
        revision_date = datetime.date(2011, 9, 25)
        filename = 'myfile'
        with pytest.raises(cvs_mod.CvsCommandException):
            self.reference_obj._cvs_update(filename,
                                           revision=revision,
                                           datetime_rev=revision_date)
        mock_cvs_command.assert_not_called()

    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_command')
    def test_cvs_update_negative(self, mock_cvs_command):
        mock_cvs_command.side_effect = cvs_mod.CvsCommandException('abc')

        with pytest.raises(cvs_mod.CvsCommandException):
            self.reference_obj._cvs_update()
        mock_cvs_command.assert_called_with('update -dP', exclusive=True)

    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_parse_cvs_update_output')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_checkout')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_update')
    def test_update_shared_repo(self,
                                mock_cvs_update,
                                mock_cvs_checkout,
                                mock_parse_cvs_output):
        mock_parse_cvs_output.return_value = []
        mock_cvs_update.return_value = ('std-out', 'std-err')

        self.reference_obj._update_shared_repo()
        mock_cvs_update.assert_called()

    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_clean_checkout_directory')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_parse_cvs_update_output')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_checkout')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_update')
    def test_update_shared_repo_with_cleanup(self,
                                             mock_cvs_update,
                                             mock_cvs_checkout,
                                             mock_parse_cvs_output,
                                             mock_clean_checkout_directory):
        mock_parse_cvs_output.side_effect = [
            ['clean/up/me/'],
            []
        ]
        mock_cvs_update.return_value = ('std-out', 'std-err')

        self.reference_obj._update_shared_repo()
        mock_cvs_update.assert_called()
        mock_clean_checkout_directory.assert_called()

    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_clean_checkout_directory')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_parse_cvs_update_output')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_checkout')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_update')
    def test_update_shared_repo_full_checkout(self,
                                              mock_cvs_update,
                                              mock_cvs_checkout,
                                              mock_parse_cvs_output,
                                              mock_clean_checkout_directory):
        mock_parse_cvs_output.side_effect = [
            ['clean/up/me/'],
            ['and/me/as/well']
        ]
        mock_cvs_update.return_value = ('std-out', 'std-err')

        self.reference_obj._update_shared_repo()
        mock_cvs_update.assert_called()
        mock_clean_checkout_directory.assert_called()
        mock_cvs_checkout.assert_called()

    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_clean_checkout_directory')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_parse_cvs_update_output')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_checkout')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_update')
    def test_update_shared_repo_cvs_failure(self,
                                            mock_cvs_update,
                                            mock_cvs_checkout,
                                            mock_parse_cvs_output,
                                            mock_clean_checkout_directory):
        mock_cvs_update.side_effect = cvs_mod.CvsCommandException('abc')

        self.reference_obj._update_shared_repo()

        mock_cvs_checkout.assert_called()

    def test_parse_cvs_update_output(self):
        cvsoutput = """
? rhel-unknown/vacations.tji
cvs update: warning: rhel-updated-wo-flag/Makefile was lost
U rhel-updated/Makefile
P rhel-patched/rhel-1-0-0.tjp
A rhel-added/rhel-1-0-0.tjp
A rhel-added/rhel-2-0-0.tjp
A rhel-added2/rhel-22-0-0.tjp
C rhel-conflict/rhel-2-0-0.tjp
M rhel-modified/rhel-3-0-0.tjp
x rhel-unknown-flag/rhel-3-0-0.tjp
"""
        to_cleanup = self.reference_obj._parse_cvs_update_output(cvsoutput)
        to_cleanup_ref = ['rhel-unknown', 'rhel-conflict', 'rhel-modified',
                          'rhel-unknown-flag', 'rhel-added', 'rhel-added2']
        assert to_cleanup == set(to_cleanup_ref)

    @mock.patch('schedules_tools.storage_handlers.cvs.os.path.exists')
    @mock.patch('schedules_tools.storage_handlers.cvs.remove_tree')
    def test_clean_checkout_directory(self, mock_remove_tree, mock_path_exists):
        directory = 'program/fedora/f-25'
        mock_path_exists.return_value = True
        self.reference_obj._clean_checkout_directory(directory)
        mock_remove_tree.assert_called_with('/tmp/mycheckoutdir/program/fedora/f-25')

    @mock.patch('schedules_tools.storage_handlers.cvs.os.path.exists')
    @mock.patch('schedules_tools.storage_handlers.cvs.remove_tree')
    def test_clean_not_existing_checkout_directory(self, mock_remove_tree, mock_path_exists):
        directory = 'program/fedora/f-25'
        mock_path_exists.return_value = False
        self.reference_obj._clean_checkout_directory(directory)
        mock_remove_tree.assert_not_called()

    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_command')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, 'refresh_local')
    def test_get_handle_changelog_cvs_fail(self,
                                           mock_refresh_local,
                                           mock_cvs_command):
        mock_cvs_command.side_effect = cvs_mod.CvsCommandException('abc')

        with pytest.raises(cvs_mod.CvsCommandException):
            self.reference_obj.get_handle_changelog()
        mock_refresh_local.assert_called()

    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_command')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, 'refresh_local')
    def test_get_handle_changelog(self,
                                  mock_refresh_local,
                                  mock_cvs_command):
        with open(os.path.join(BASE_DIR, 'fixtures', 'cvs_log.stdout')) as fd:
            cvs_stdout = fd.read()

        with open(os.path.join(BASE_DIR, 'fixtures', 'cvs_log.json')) as fd:
            changelog_ref = jsondate.load(fd)

        mock_cvs_command.return_value = (cvs_stdout, 'stderr')

        changelog = self.reference_obj.get_handle_changelog()
        assert changelog_ref == changelog
        mock_refresh_local.assert_called()

    @mock.patch('redis.StrictRedis')
    def test_cvs_command_exclusive_access_default_redis_config(
            self,
            mock_redis):
        options = {
            'cvs_repo_name': 'program',
            'cvs_root': ':gserver:someuser@cvs.myserver.com:/cvs/reporoot',
            'cvs_checkout_path': '/tmp/a/b/cc',
            'exclusive_access': True,
        }
        handle = 'program/product/release/release.tjp'
        reference = cvs_mod.StorageHandler_cvs(
            handle,
            options=options)
        mock_redis.assert_called_with()

    @mock.patch('redis.StrictRedis.from_url')
    def test_cvs_command_exclusive_access_custom_redis_config(
            self,
            mock_redis_from_url):
        options = {
            'cvs_repo_name': 'repo',
            'cvs_root': ':gserver:someuser@cvs.myserver.com:/cvs/reporoot',
            'cvs_checkout_path': '/tmp/a/b/cc',
            'exclusive_access': True,
            'redis_url': 'redis://redishost:1234/5'
        }
        handle = 'program/product/release/release.tjp'
        reference = cvs_mod.StorageHandler_cvs(
            handle,
            options=options)
        mock_redis_from_url.assert_called_with('redis://redishost:1234/5')

    @mock.patch('redis.StrictRedis')
    def test_cvs_command_exclusive_access_incorrect_custom_redis_config(
            self,
            mock_redis):
        options = {
            'cvs_repo_name': 'repo',
            'cvs_root': ':gserver:someuser@cvs.myserver.com:/cvs/reporoot',
            'cvs_checkout_path': '/tmp/a/b/cc',
            'exclusive_access': True,
            'cvs_lock_redis_uri': 'http://redishost:1234/5'
        }
        handle = 'program/product/release/release.tjp'
        reference = cvs_mod.StorageHandler_cvs(
            handle,
            options=options)
        mock_redis.assert_called_with()

    @mock.patch('redis.StrictRedis')
    @mock.patch('schedules_tools.storage_handlers.cvs.subprocess.Popen')
    def test_cvs_command_exclusive_access(self,
                                          mock_popen,
                                          mock_redis):
        options = {
            'cvs_repo_name': 'root',
            'cvs_root': ':gserver:someuser@cvs.myserver.com:/cvs/reporoot',
            'cvs_checkout_path': '/tmp/a/b/cc',
            'exclusive_access': True,
        }
        handle = 'program/product/release/release.tjp'

        cmd = 'update program/rhel'
        mock_communicate = mock.Mock()
        mock_communicate.communicate.return_value = ('stdo', 'stde')
        mock_popen.return_value = mock_communicate
        type(mock_communicate).returncode = mock.PropertyMock(return_value=0)

        mock_redis_inst = mock.Mock()
        mock_redis.return_value = mock_redis_inst

        mock_lock = mock.Mock()
        mock_redis_inst.lock.return_value = mock_lock

        reference = cvs_mod.StorageHandler_cvs(
            handle,
            options=options)
        assert reference._cvs_command(cmd, exclusive=True) == ('stdo', 'stde')
        mock_popen.assert_called()
        mock_lock.acquire.assert_called()
        mock_lock.release.assert_called()

    @mock.patch('redis.StrictRedis')
    def test_cvs_command_exclusive_access_unable_acquire(self, mock_redis):
        options = {
            'cvs_repo_name': 'repo',
            'cvs_root': ':gserver:someuser@cvs.myserver.com:/cvs/reporoot',
            'cvs_checkout_path': '/tmp/a/b/cc',
            'exclusive_access': True,
        }
        handle = 'program/product/release/release.tjp'

        cmd = 'update program/rhel'

        mock_redis_inst = mock.Mock()
        mock_redis.return_value = mock_redis_inst

        mock_acquire = mock.Mock(return_value=False)
        mock_lock = mock.Mock()
        mock_lock.acquire = mock_acquire
        mock_redis_inst.lock.return_value = mock_lock

        reference = cvs_mod.StorageHandler_cvs(
            handle,
            options=options)

        with pytest.raises(storage_handlers.AcquireLockException):
            reference._cvs_command(cmd, exclusive=True)

    @mock.patch('shutil.move')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_wipe_out_dir')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_is_valid_cvs_dir')
    def test_checkout_dir_by_opt_arg(self,
                                     mock_is_valid_cvs_dir,
                                     mock_wipe_out_dir,
                                     mock_shutil_move):
        options = {
            'cvs_repo_name': 'repo',
            'cvs_root': ':gserver:someuser@cvs.myserver.com:/cvs/reporoot',
            'cvs_checkout_path': '/tmp/a/b/cc'
        }
        handle = 'program/product/release/release.tjp'
        reference = cvs_mod.StorageHandler_cvs(
            handle,
            options=options)

        assert reference._cvs_checkout() == '/tmp/a/b/cc'

    @mock.patch('shutil.move')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_wipe_out_dir')
    @mock.patch('tempfile.mkdtemp')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_command')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_is_valid_cvs_dir')
    def test_checkout_dir_by_opt_arg_force(self,
                                           mock_is_valid_cvs_dir,
                                           mock_cvs_command,
                                           mock_mkdtemp,
                                           mock_wipe_out_dir,
                                           mock_shutil_move):
        options = {
            'cvs_repo_name': 'repo',
            'cvs_root': ':gserver:someuser@cvs.myserver.com:/cvs/reporoot',
            'cvs_checkout_path': '/tmp/somepath',
        }
        handle = 'program/product/release/release.tjp'
        reference = cvs_mod.StorageHandler_cvs(
            handle,
            options=options)

        mock_is_valid_cvs_dir.return_value = True
        mock_cvs_command.return_value = ('stdout', 'stderr')

        assert reference._cvs_checkout(force=True) == '/tmp/somepath'
        mock_mkdtemp.assert_called()
        mock_wipe_out_dir.assert_called()
        mock_shutil_move.assert_called()
        mock_cvs_command.assert_called()

    @mock.patch('shutil.move')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_wipe_out_dir')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_cvs_command')
    @mock.patch.object(cvs_mod.StorageHandler_cvs, '_is_valid_cvs_dir')
    @mock.patch('tempfile.mkdtemp')
    def test_checkout_dir_mkdtemp(self,
                                  mock_mkdtemp,
                                  mock_is_valid_cvs_dir,
                                  mock_cvs_command,
                                  mock_wipe_out_dir,
                                  mock_shutil_move):
        options = {
            'cvs_repo_name': 'repo',
            'cvs_root': ':gserver:someuser@cvs.myserver.com:/cvs/reporoot',
            'cvs_checkout_path': None,
        }
        handle = 'program/product/release/release.tjp'
        reference = cvs_mod.StorageHandler_cvs(handle, options=options)

        mock_mkdtemp.side_effect = ['/temp/repo', '/temp/temp_cloed_repo']

        mock_is_valid_cvs_dir.return_value = True

        mock_cvs_command.return_value = ('stdout', 'stderr')

        assert reference._cvs_checkout() == '/temp/repo'
        mock_mkdtemp.assert_called()
        mock_wipe_out_dir.assert_called()
        mock_shutil_move.assert_called()
