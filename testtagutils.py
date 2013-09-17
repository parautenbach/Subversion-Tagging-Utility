#!/usr/local/bin/python2.7
# Copyright 2013 Pieter Rautenbach
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#   http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
import os
import sys
import shutil
import pysvn
import svnerr
import tagutils
import tagtrunk

class TestTagUtils(unittest.TestCase):

    def setUp(self):
        tagutils.SUPPRESS_STD_OUT = True

    def tearDown(self):
        buildDir = './test/trunk/build'
        if os.path.exists(buildDir):
            os.rmdir(buildDir)

    def test_normalise_relative_path(self):
        # Empty path must yield /
        self.assertEqual(tagutils.normalise_relative_path(''), '/')
        self.assertEqual(tagutils.normalise_relative_path('.'), '/')
        # Leading forward slash must be removed
        self.assertEqual(tagutils.normalise_relative_path('/abc/'), '/abc')
        # Leading backward slash must become forward slash
        self.assertEqual(tagutils.normalise_relative_path('\\abc'), '/abc')
        # Inner backward slash must become forward slash
        self.assertEqual(tagutils.normalise_relative_path('\\abc\\def'), '/abc/def')
        # Mixture must yield only forward slashes
        self.assertEqual(tagutils.normalise_relative_path('/abc\\def'), '/abc/def')
        # Multiple slashes must be collapsed
        self.assertEqual(tagutils.normalise_relative_path('\\abc\\\\def'), '/abc/def')
        self.assertEqual(tagutils.normalise_relative_path('\\abc\\\\\\def'), '/abc/def')
        self.assertEqual(tagutils.normalise_relative_path('\\abc\\\\\\def\\ghi'), '/abc/def/ghi')
        self.assertEqual(tagutils.normalise_relative_path('/abc//def'), '/abc/def')
        self.assertEqual(tagutils.normalise_relative_path('\\\\src'), '/src')
        # Trailing slashes must be removed
        self.assertEqual(tagutils.normalise_relative_path('/abc/def/'), '/abc/def')
        self.assertEqual(tagutils.normalise_relative_path('\\abc\\def\\'), '/abc/def')
        self.assertEqual(tagutils.normalise_relative_path('\\abc\\def\\\\'), '/abc/def')
        # Leading forward slash must exist
        self.assertEqual(tagutils.normalise_relative_path('abc\\def'), '/abc/def')
        self.assertEqual(tagutils.normalise_relative_path('abc/def'), '/abc/def')

    def test_is_version_number(self):
        # Valid version numbers
        self.assertTrue(tagutils.is_version_number('1.0.0.0'))
        self.assertTrue(tagutils.is_version_number('0.1.0.0'))
        self.assertTrue(tagutils.is_version_number('0.0.1.0'))
        self.assertTrue(tagutils.is_version_number('0.0.0.1'))
        self.assertTrue(tagutils.is_version_number('11.0.0.0'))
        self.assertTrue(tagutils.is_version_number('111.0.0.0'))
        # Not 4 parts
        self.assertFalse(tagutils.is_version_number('1.0.0'))
        self.assertFalse(tagutils.is_version_number('1.0'))
        self.assertFalse(tagutils.is_version_number('1'))
        # Trailing .
        self.assertFalse(tagutils.is_version_number('1.0.0.0.'))
        self.assertFalse(tagutils.is_version_number('1.0.0.'))
        self.assertFalse(tagutils.is_version_number('1.0.'))
        self.assertFalse(tagutils.is_version_number('1.'))
        # Leading .
        self.assertFalse(tagutils.is_version_number('.1.0.0.0'))
        self.assertFalse(tagutils.is_version_number('.1.0.0'))
        self.assertFalse(tagutils.is_version_number('.1.0'))
        self.assertFalse(tagutils.is_version_number('.1'))
        # Contains alpha
        self.assertFalse(tagutils.is_version_number('a.0.0.0'))
        self.assertFalse(tagutils.is_version_number('0.a.0.0'))
        self.assertFalse(tagutils.is_version_number('0.0.a.0'))
        self.assertFalse(tagutils.is_version_number('0.0.0.a'))
        # Contains negative
        self.assertFalse(tagutils.is_version_number('-1.0.0.0'))

    def test_get_repository_info(self):
        # Repo project path is NOT a trunk path
        path = 'C:\\don\'t\\care'
        client = MockPySvn('/dummy/project', path)
        repo_info = tagutils.get_repository_info(client, path)
        self.assertIsNone(repo_info)
        # Repo project IS a trunk path
        path = 'C:\\dummy\\project\\trunk'
        client = MockPySvn('/dummy/project/trunk', path)
        repo_info = tagutils.get_repository_info(client, path)
        self.assertEqual(repo_info['trunk_dir'], path)
        # Raise exception
        path = 'C:\\foo\\project\\trunk'
        client = MockPySvn('/foo/project/trunk', path)
        self.assertIsNone(tagutils.get_repository_info(client, path))
        # Repo project CONTAINS a trunk path
        if sys.platform == 'win32':
            client = MockPySvn('/dummy/project/trunk/src', '')
            path = 'C:\\dummy\\project\\trunk\\src'
            repo_info = tagutils.get_repository_info(client, path)
            (path, _, _) = path.rpartition('\\')
            self.assertEqual(repo_info['trunk_dir'], path)
        else:
            client = MockPySvn('/dummy/project/trunk/src', '')
            path = '/tmp/dummy/project/trunk/src'
            repo_info = tagutils.get_repository_info(client, path)
            (path, _, _) = path.rpartition('/')
            self.assertEqual(repo_info['trunk_dir'], path)
        # Repo URL contains a trunk, but path can't traverse up
        if sys.platform == 'win32':
            client = MockPySvn('/dummy/project/trunk/src', '')
            path = 'C:\\'
            repo_info = tagutils.get_repository_info(client, path)
            self.assertIsNone(repo_info)
        else:
            client = MockPySvn('/dummy/project/trunk/src', '')
            path = '/'
            repo_info = tagutils.get_repository_info(client, path)
            self.assertIsNone(repo_info)

    def test_assign_params(self):
        self.maxDiff = None
        # Simple case: All well defined
        if sys.platform == 'win32':
            repo_info = {'trunk_url': 'http://foo/trunk', 'trunk_dir': 'C:\\Foo\\trunk'}
            args = MockArgs('1.0.0.0', 'src', 'build', 'bin\\Debug', 'dev')
            param_dict_expected = {'Name': 'foo',
                                   'Version': '1.0.0',
                                   'Tag Type': 'dev',
                                   'Trunk': 'C:\\Foo\\trunk',
                                   'Source': '/src',
                                   'Build': '/build',
                                   'Build Source': 'bin\\Debug',
                                   'Build Source Full': 'C:\\Foo\\trunk\\bin\\Debug',
                                   'Root URL': 'http://foo',
                                   'Trunk URL': 'http://foo/trunk',
                                   'Tag URL': 'http://foo/tags/foo-1.0.0-dev',
                                   'Tag Source URL': 'http://foo/tags/foo-1.0.0-dev/src',
                                   'Tag Build URL': 'http://foo/tags/foo-1.0.0-dev/build'}
        else:
            repo_info = {'trunk_url': 'http://foo/trunk', 'trunk_dir': '/tmp/foo/trunk'}
            args = MockArgs('1.0.0.0', 'src', 'build', 'bin/debug', 'dev')
            param_dict_expected = {'Name': 'foo',
                                   'Version': '1.0.0',
                                   'Tag Type': 'dev',
                                   'Trunk': '/tmp/foo/trunk',
                                   'Source': '/src',
                                   'Build': '/build',
                                   'Build Source': 'bin/debug',
                                   'Build Source Full': '/tmp/foo/trunk/bin/debug',
                                   'Root URL': 'http://foo',
                                   'Trunk URL': 'http://foo/trunk',
                                   'Tag URL': 'http://foo/tags/foo-1.0.0-dev',
                                   'Tag Source URL': 'http://foo/tags/foo-1.0.0-dev/src',
                                   'Tag Build URL': 'http://foo/tags/foo-1.0.0-dev/build'}
        param_dict = {}
        tagutils.assign_params(repo_info, args, param_dict)
        self.assertDictEqual(param_dict_expected, param_dict)
        # No source/source goes to trunk
        if sys.platform == 'win32':
            repo_info = {'trunk_url': 'http://foo/trunk', 'trunk_dir': 'C:\\Foo\\trunk'}
            args = MockArgs('1.0.0.0', '/', 'build', 'bin\\Debug', 'dev')
            param_dict_expected = {'Name': 'foo',
                                   'Version': '1.0.0',
                                   'Tag Type': 'dev',
                                   'Trunk': 'C:\\Foo\\trunk',
                                   'Source': '/',
                                   'Build': '/build',
                                   'Build Source': 'bin\\Debug',
                                   'Build Source Full': 'C:\\Foo\\trunk\\bin\\Debug',
                                   'Root URL': 'http://foo',
                                   'Trunk URL': 'http://foo/trunk',
                                   'Tag URL': 'http://foo/tags/foo-1.0.0-dev',
                                   'Tag Source URL': 'http://foo/tags/foo-1.0.0-dev',
                                   'Tag Build URL': 'http://foo/tags/foo-1.0.0-dev/build'}
        else:
            repo_info = {'trunk_url': 'http://foo/trunk', 'trunk_dir': '/tmp/foo/trunk'}
            args = MockArgs('1.0.0.0', '/', 'build', 'bin/debug', 'dev')
            param_dict_expected = {'Name': 'foo',
                                   'Version': '1.0.0',
                                   'Tag Type': 'dev',
                                   'Trunk': '/tmp/foo/trunk',
                                   'Source': '/',
                                   'Build': '/build',
                                   'Build Source': 'bin/debug',
                                   'Build Source Full': '/tmp/foo/trunk/bin/debug',
                                   'Root URL': 'http://foo',
                                   'Trunk URL': 'http://foo/trunk',
                                   'Tag URL': 'http://foo/tags/foo-1.0.0-dev',
                                   'Tag Source URL': 'http://foo/tags/foo-1.0.0-dev',
                                   'Tag Build URL': 'http://foo/tags/foo-1.0.0-dev/build'}
        param_dict = {}
        tagutils.assign_params(repo_info, args, param_dict)
        self.assertDictEqual(param_dict_expected, param_dict)
        # NOTE: PUT TESTS THAT SET THE ENVIRONMENT VARIABLE FROM HERE
        # Overwrite using environment variable for tagging type (dev -> rc1)
        os.environ[tagutils.EXECUTE_TAGGING_TYPE] = 'rc1'
        if sys.platform == 'win32':
            repo_info = {'trunk_url': 'http://foo/trunk', 'trunk_dir': 'C:\\Foo\\trunk'}
            args = MockArgs('1.0.0.0', 'src', 'build', 'bin\\Debug', 'dev')
            param_dict_expected = {'Name': 'foo',
                                   'Version': '1.0.0.0',
                                   'Tag Type': 'rc1',
                                   'Trunk': 'C:\\Foo\\trunk',
                                   'Source': '/src',
                                   'Build': '/build',
                                   'Build Source': 'bin\\Debug',
                                   'Build Source Full': 'C:\\Foo\\trunk\\bin\\Debug',
                                   'Root URL': 'http://foo',
                                   'Trunk URL': 'http://foo/trunk',
                                   'Tag URL': 'http://foo/tags/foo-1.0.0.0-rc1',
                                   'Tag Source URL': 'http://foo/tags/foo-1.0.0.0-rc1/src',
                                   'Tag Build URL': 'http://foo/tags/foo-1.0.0.0-rc1/build'}
        else:
            repo_info = {'trunk_url': 'http://foo/trunk', 'trunk_dir': '/tmp/foo/trunk'}
            args = MockArgs('1.0.0.0', 'src', 'build', 'bin/debug', 'dev')
            param_dict_expected = {'Name': 'foo',
                                   'Version': '1.0.0.0',
                                   'Tag Type': 'rc1',
                                   'Trunk': '/tmp/foo/trunk',
                                   'Source': '/src',
                                   'Build': '/build',
                                   'Build Source': 'bin/debug',
                                   'Build Source Full': '/tmp/foo/trunk/bin/debug',
                                   'Root URL': 'http://foo',
                                   'Trunk URL': 'http://foo/trunk',
                                   'Tag URL': 'http://foo/tags/foo-1.0.0.0-rc1',
                                   'Tag Source URL': 'http://foo/tags/foo-1.0.0.0-rc1/src',
                                   'Tag Build URL': 'http://foo/tags/foo-1.0.0.0-rc1/build'}
        param_dict = {}
        tagutils.assign_params(repo_info, args, param_dict)
        self.assertDictEqual(param_dict_expected, param_dict)
        # Using empty environment variable for tagging type
        os.environ[tagutils.EXECUTE_TAGGING_TYPE] = ''
        if sys.platform == 'win32':
            repo_info = {'trunk_url': 'http://foo/trunk', 'trunk_dir': 'C:\\Foo\\trunk'}
            args = MockArgs('1.0.0.0', 'src', 'build', 'bin\\Debug', 'dev')
            param_dict_expected = {'Name': 'foo',
                                   'Version': '1.0.0.0',
                                   'Tag Type': 'final',
                                   'Trunk': 'C:\\Foo\\trunk',
                                   'Source': '/src',
                                   'Build': '/build',
                                   'Build Source': 'bin\\Debug',
                                   'Build Source Full': 'C:\\Foo\\trunk\\bin\\Debug',
                                   'Root URL': 'http://foo',
                                   'Trunk URL': 'http://foo/trunk',
                                   'Tag URL': 'http://foo/tags/foo-1.0.0.0-final',
                                   'Tag Source URL': 'http://foo/tags/foo-1.0.0.0-final/src',
                                   'Tag Build URL': 'http://foo/tags/foo-1.0.0.0-final/build'}
        else:
            repo_info = {'trunk_url': 'http://foo/trunk', 'trunk_dir': '/tmp/foo/trunk'}
            args = MockArgs('1.0.0.0', 'src', 'build', 'bin/debug', 'dev')
            param_dict_expected = {'Name': 'foo',
                                   'Version': '1.0.0.0',
                                   'Tag Type': 'final',
                                   'Trunk': '/tmp/foo/trunk',
                                   'Source': '/src',
                                   'Build': '/build',
                                   'Build Source': 'bin/debug',
                                   'Build Source Full': '/tmp/foo/trunk/bin/debug',
                                   'Root URL': 'http://foo',
                                   'Trunk URL': 'http://foo/trunk',
                                   'Tag URL': 'http://foo/tags/foo-1.0.0.0-final',
                                   'Tag Source URL': 'http://foo/tags/foo-1.0.0.0-final/src',
                                   'Tag Build URL': 'http://foo/tags/foo-1.0.0.0-final/build'}
        param_dict = {}
        tagutils.assign_params(repo_info, args, param_dict)
        self.assertDictEqual(param_dict_expected, param_dict)

    def test_create_tag(self):
        client = MockPySvn('', '')
        # Normal execution
        self.assertTrue(tagutils.create_tag(client,
                                            'foo',
                                            '1.0.0.0',
                                            'http://foo/trunk',
                                            'http://foo/tags/foo-1.0.0.0-final',
                                            'http://foo/tags/foo-1.0.0.0-final/src'))
        # Conflict
        self.assertFalse(tagutils.create_tag(client,
                                             'bar',
                                             '1.0.0.0',
                                             'http://bar/trunk',
                                             'http://bar/tags/bar-1.0.0.0-final',
                                             'http://bar/tags/bar-1.0.0.0-final/src'))
        # No parent mkdir required - successful path
        self.assertTrue(tagutils.create_tag(client,
                                            'qux',
                                            '1.0.0.0',
                                            'http://qux/trunk',
                                            'http://qux/tags/qux-1.0.0.0-final',
                                            'http://qux/tags/qux-1.0.0.0-final'))
        # No parent mkdir required - will fail
        self.assertFalse(tagutils.create_tag(client,
                                             'qux',
                                             '1.0.0.0',
                                             'http://qux/trunk',
                                             'http://qux/tags/qux-1.0.0.0-final',
                                             'http://qux/tags/qux-1.0.0.0-final/src'))
        # Unexpected
        with self.assertRaises(pysvn.ClientError):
            tagutils.create_tag(client,
                                'baz',
                                '1.0.0.0',
                                'http://baz/trunk',
                                'http://baz/tags/baz-1.0.0.0-final',
                                'http://baz/tags/baz-1.0.0.0-final/src')

    def test_import_artifacts(self):
        client = MockPySvn('', '')
        # No such path
        self.assertFalse(tagutils.import_artifacts(client, 'foo', '1.0.0.0', 'C:\\foo\\bin\\Debug', 'http://foo/tags/foo-1.0.0.0-final/build'))
        # Exists
        buildDir = './test/trunk/build'
        os.mkdir(buildDir)
        self.assertTrue(tagutils.import_artifacts(client, 'foo', '1.0.0.0', buildDir, 'http://foo/tags/foo-1.0.0.0-final/build'))
        os.rmdir(buildDir)

    def test_remove_dev_tag(self):
        client = MockPySvn('', '')
        # Normal execution where tag exists
        self.assertIsNone(tagutils.remove_dev_tag(client, 'http://foo/tags/foo-1.0.0-dev'))
        # Normal execution where tag doesn't exist
        self.assertIsNone(tagutils.remove_dev_tag(client, 'http://bar/tags/bar-1.0.0-dev'))
        # Unpexpected
        with self.assertRaises(pysvn.ClientError):
            tagutils.remove_dev_tag(client, 'http://baz/tags/baz-1.0.0-dev')

    def test_validate_args(self):
        args = MockArgs('1.0.0.0', 'src', 'build', 'bin\\Debug', 'dev')
        self.assertTrue(tagutils.validate_args(args)[0])
        args = MockArgs('1.0.0', 'src', 'build', 'bin\\Debug', 'dev')
        self.assertFalse(tagutils.validate_args(args)[0])

    def test_setup_svn_client(self):
        client = tagutils.setup_svn_client('', '')
        info = client.info('')
        self.assertTrue(info.commit_revision.number > 0)

    def test_tagtrunk(self):
        devnull = open(os.devnull, 'w')
        prog = 'tagtrunk.py'
        # Invalid command-line SYNTAX; must exit with error code 2
        sys.argv = []
        sys.argv.append(prog) # prog
        with self.assertRaises(SystemExit) as se:
            tagtrunk.main()
        self.assertEqual(int(str(se.exception)), 2)
        # Invalid version number (ARGUMENTS)
        sys.argv = []
        sys.argv.append(prog) # prog
        sys.argv.append('1.0.0') # V
        sys.argv.append('.') # S
        with self.assertRaises(SystemExit) as se:
            tagtrunk.main()
        self.assertEqual(int(str(se.exception)), 1)
        # No repo info
        sys.argv = []
        sys.argv.append(prog) # prog
        sys.argv.append('1.0.0.0') # V
        sys.argv.append('.') # S
        with self.assertRaises(SystemExit) as se:
            tagtrunk.main()
        self.assertEqual(int(str(se.exception)), 1)
        # Create a dev tag
        # We need to operate from here to have a valid trunk
        cwd = os.getcwd()
        os.chdir('./test/trunk')
        # Create a fake build artifact
        buildDir = 'build'
        os.mkdir('./{0}'.format(buildDir))
        f = open('./{0}/bin.dll'.format(buildDir), 'a')
        f.close()
        # Overwrite command-line
        os.environ[tagutils.EXECUTE_TAGGING_TYPE] = 'dev'
        sys.argv = []
        sys.argv.append(prog) # prog
        sys.argv.append('1.0.0.0') # V
        sys.argv.append('src') # S
        sys.argv.append(buildDir) # B
        sys.argv.append(buildDir) # BS
        sys.argv.append('final') # T -- will get overwritten
        with self.assertRaises(SystemExit) as se:
            tagtrunk.main()
        self.assertEqual(int(str(se.exception)), 0)
        shutil.rmtree('./{0}'.format(buildDir))
        os.chdir(cwd)
        # Try to import artifacts that cannot be found
        # We need to operate from here to have a valid trunk
        cwd = os.getcwd()
        os.chdir('./test/trunk')
        sys.argv = []
        sys.argv.append(prog) # prog
        sys.argv.append('1.0.0.0') # V
        sys.argv.append('src') # S
        sys.argv.append(buildDir) # B
        sys.argv.append(buildDir) # BS
        sys.argv.append('final') # T -- will get overwritten
        with self.assertRaises(SystemExit) as se:
            tagtrunk.main()
        self.assertEqual(int(str(se.exception)), 1)
        os.chdir(cwd)
        # Try to create a final tag that exists
        cwd = os.getcwd()
        os.chdir('./test/trunk')
        os.environ[tagutils.EXECUTE_TAGGING_TYPE] = 'final'
        sys.argv = []
        sys.argv.append(prog) # prog
        sys.argv.append('1.0.0.0') # V
        sys.argv.append('src') # S
        sys.argv.append(buildDir) # B
        sys.argv.append(buildDir) # BS
        sys.argv.append('final') # T -- will get overwritten
        with self.assertRaises(SystemExit) as se:
            tagtrunk.main()
        self.assertEqual(int(str(se.exception)), 1)
        os.chdir(cwd)
 
class MockRevision():
    def __init__(self):
        self.number = 1

class MockPySvn():
    """Class that mocks pysvn for unit testing.
    """

    def __init__(self, repo_project_path, project_path):
        self.repos_root_URL = 'http://dummy.svn.root.url'
        self.full_repo_project_path = '{0}{1}'.format(self.repos_root_URL, repo_project_path)
        self.project_path = project_path
        self.fail_qux = False

    def info2(self, path, recurse=True):
        """Mock method of pysvn. Everytime info2 gets called, it will slice
        the last part of the path/URL. This emulates getting a matching URL/path
        pair everytime we visit the parent (which is what happens in get_repository_info.
        """
        if 'foo' in path:
            ce = pysvn.ClientError()
            msg = 'Dummy exception for getting info'
            ce.args = (msg, [(msg, -1)])
            raise(ce)
        info = {'repos_root_URL': self.repos_root_URL,
                'URL': self.full_repo_project_path}
        (self.full_repo_project_path, _, _) = self.full_repo_project_path.rpartition('/')
        (self.project_path, _, _) = self.project_path.rpartition('/')
        return [(path, info)]

    def mkdir(self, url, log_message):
        if 'qux' in url:
            self.fail_qux = True

    def copy(self, from_url, to_url):
        self.copy2(from_url, to_url)

    def copy2(self, sources, tag_source_url, make_parents=False):
        if 'bar' in tag_source_url or self.fail_qux:
            self.fail_qux = False
            ce = pysvn.ClientError()
            msg = 'Dummy exception for path exists'
            ce.args = (msg, [(msg, svnerr.FS_ALREADY_EXISTS)])
            raise(ce)
        elif 'baz' in tag_source_url:
            ce = pysvn.ClientError()
            msg = 'Dummy exception for unexpected error'
            ce.args = (msg, [(msg, -1)])
            raise(ce)

    def import_(self, path, url, log_message):
        return MockRevision()

    def remove(self, url):
        if 'bar' in url:
            ce = pysvn.ClientError()
            msg = 'Dummy exception for path exists'
            ce.args = (msg, [(msg, svnerr.FS_NOT_FOUND)])
            raise(ce)
        elif 'baz' in url:
            ce = pysvn.ClientError()
            msg = 'Dummy exception for unexpected error'
            ce.args = (msg, [(msg, -1)])
            raise(ce)

class MockArgs():
    """Class that mocks Python's argument parser."""

    def __init__(self, V, S, B, BS, T):
        self.V = V
        self.S = S
        self.B = B
        self.BS = BS
        self.T = T

if __name__ == '__main__':
    # Produces more verbose output than unittest.main()
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTagUtils)
    unittest.TextTestRunner(verbosity=2).run(suite)

# Snippets of code useful for debugging:
# Snippet 1
#tmp = tagutils.SUPPRESS_STD_OUT
#tagutils.SUPPRESS_STD_OUT = False
#<do stuff>
#tagutils.SUPPRESS_STD_OUT = tmp
# Snippet 2
#sys.stdout = devnull
#sys.stderr = devnull
#<do stuff>
#sys.stdout = sys.__stdout__
#sys.stderr = sys.__stderr__
