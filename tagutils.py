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

import argparse
import os.path
import sys
import svnerr
import pysvn

"""Script used by TeamCity to automate the tagging of a project.
"""

# Overwriting environment variable (usually passed via TeamCity)
EXECUTE_TAGGING_TYPE = 'EXECUTE_TAGGING_TYPE'
# Default tag type
DEFAULT_TAG_TYPE = 'final'
# Set to True e.g. when running unit tests
SUPPRESS_STD_OUT = False
# Subversion path separator
SVN_SEP = '/'
# Version number separator
VER_SEP = '.'

def setup_argument_parser():
    """Setup the command-line argument parser's parameters, help, etc.
    """
    __print_if_not_suppressed('Setting up argument parser')
    prog = os.path.basename(sys.argv[0])
    parser = argparse.ArgumentParser(description='Tag a build in a Subversion repository.',
                                     epilog='Example: {0} 1.0.0.0 src build build_project/bin/Release final'.format(prog))
    parser.add_argument('V',
                        help='the version of the application in the format <major>.<minor>.<revision>.<build>')
    parser.add_argument('S',
                        help='the target directory in the repository where the source code must go')
    parser.add_argument('B',
                        nargs='?',
                        default='build',
                        help='the target build directory in the repository')
    parser.add_argument('BS',
                        nargs='?',
                        default='',
                        help='the source directory on disk which will be added to the repository in the build directory')
    parser.add_argument('T',
                        nargs='?',
                        default=DEFAULT_TAG_TYPE,
                        help='type of tag (dev, rc<no> or final); the default is final')
    return parser

def validate_args(args):
    """Check whether specific parameters are valid.

    Returns a tuple (valid, errorMessage), where valid=True/False
    and errorMessage will be populated if invalid (or valid=False)
    """
    __print_if_not_suppressed('Validating command-line arguments')
    if not is_version_number(args.V):
        return (False, 'Invalid version number {0}'.format(args.V))
    return (True, '')

def setup_svn_client(username, password):
    """Create and configure an instance of a SVN client.
    """
    __print_if_not_suppressed('Setting up Subversion client')
    client = pysvn.Client()
    client.set_store_passwords(False)
    client.set_auth_cache(False)
    client.set_default_username(username)
    client.set_default_password(password)
    client.exception_style = 1
    return client

def get_repository_info(svnClient, directory):
    """Retrieve the repository's root and find the server trunk URL that
    matches the trunk in the working copy.
    """
    __print_if_not_suppressed('Getting repository info and traversing working copy path to find trunk')
    while True:
        try:
            (path, info) = svnClient.info2(directory, recurse=False)[0]
        except pysvn.ClientError as ce:
            (msg, error) = ce.args[1][0]
            __print_if_not_suppressed('\tError getting info from Subversion: {0} ({1})'.format(msg, error))
            return None
        if info['URL'].endswith('/trunk'):
            __print_if_not_suppressed('\t{0} IS trunk'.format(directory))
            repoInfo = {'server_root': info['repos_root_URL'],
                        'trunk_url': info['URL'],
                        'trunk_dir': directory}
            print_repository_info(repoInfo)
            return repoInfo
        else:
            __print_if_not_suppressed('\t{0} is NOT trunk'.format(directory))
        # traverse up the tree
        currentDir = directory
        directory = __get_parent_dir(directory)
        # also stop recursion when reaching path's root
        # (i.e. the parent equals the current directory)
        if __is_same_path(directory, currentDir):
            __print_if_not_suppressed('\tReached path root')
            return None

def __is_same_path(path1, path2):
    """Check whether two paths are identical.
    """
    return path1 == path2

def __get_parent_dir(directory):
    """Return the parent of a given directory.
    """
    return os.path.dirname(directory)

def print_repository_info(repoInfo):
    """Print repository information to stdout.
    """
    __print_if_not_suppressed('Repository info')
    __print_if_not_suppressed('\tServer Root: {0}'.format(repoInfo['server_root']))
    __print_if_not_suppressed('\tTrunk URL:   {0}'.format(repoInfo['trunk_url']))
    __print_if_not_suppressed('\tTrunk Dir:   {0}'.format(repoInfo['trunk_dir']))

def print_script_parameters(param_dict):
    """Print the script's command-line parameters to stdout.
    """
    __print_if_not_suppressed('Script parameters')
    # Tag info
    __print_if_not_suppressed('\tName:              {0}'.format(param_dict['Name']))
    __print_if_not_suppressed('\tVersion:           {0}'.format(param_dict['Version']))
    __print_if_not_suppressed('\tTag Type:          {0}'.format(param_dict['Tag Type']))
    # Disk paths
    __print_if_not_suppressed('\tTrunk:             {0}'.format(param_dict['Trunk']))
    __print_if_not_suppressed('\tSource:            {0}'.format(param_dict['Source']))
    __print_if_not_suppressed('\tBuild:             {0}'.format(param_dict['Build']))
    __print_if_not_suppressed('\tBuild Source:      {0}'.format(param_dict['Build Source']))
    __print_if_not_suppressed('\tBuild Source Full: {0}'.format(param_dict['Build Source Full']))
    # URLs
    __print_if_not_suppressed('\tRoot URL:          {0}'.format(param_dict['Root URL']))
    __print_if_not_suppressed('\tTrunk URL:         {0}'.format(param_dict['Trunk URL']))
    __print_if_not_suppressed('\tTag URL:           {0}'.format(param_dict['Tag URL']))
    __print_if_not_suppressed('\tTag Source URL:    {0}'.format(param_dict['Tag Source URL']))
    __print_if_not_suppressed('\tTag Build URL:     {0}'.format(param_dict['Tag Build URL']))

def print_teamcity_info_message(message):
    """Print an informational TeamCity server message to stdout.
    """
    __print_if_not_suppressed('##teamcity[message text=\'{0}\']'.format(message))

def print_teamcity_error_message(errorDetails):
    """Print an error TeamCity server message to stdout.
    """
    __print_if_not_suppressed('##teamcity[message text=\'Tagging process failed\' errorDetails=\'{0}\' status=\'ERROR\']'.format(errorDetails))
    __print_if_not_suppressed('##teamcity[buildStatus status=\'FAILURE\']')

def is_dev_tag(tag):
    """Check whether the given tag is a development (temporary) tag.
    """
    return tag == 'dev'

def is_version_number(version):
    """Check whether the version number is in the format <major>.<minor>.<revision>.<build>
    and that all parts are digits.
    """
    vSplit = version.split(VER_SEP)
    return (len(vSplit) == 4) and (sum([x.isdigit() for x in vSplit]) == 4)

def __env_var_exists(envVar):
    """Check whether an environment variable exists.
    """
    return not os.getenv(envVar) is None

def normalise_relative_path(path):
    """Normalise a path as follows:
    1. it has a single leading forward slash,
    2. all separators are forward slashes,
    3. there are no duplicate separators in the path,
    4. there are no trailing separators,
    5. an empty path yields /.
    """
    # Requirement 5
    if path == '' or path == '.':
        return SVN_SEP
    # Requirement 3
    while '\\\\' in path:
        path = path.replace('\\\\', SVN_SEP)
    # Convert relative path from Windows to POSIX
    # Requirement 2
    path = path.replace('\\', SVN_SEP)
    # Requirement 3 (again)
    # If we have e.g. \\\\src, it will now be //src, but we can't
    # call normpath again, since that will convert the / back to \,
    # so we need to strip duplicate /'s.
    while '//' in path:
        path = path.replace('//', SVN_SEP)
    # Requirement 4
    if path.endswith(SVN_SEP):
        path = path[:-1]
    # Requirement 1
    if not path.startswith(SVN_SEP):
        path = '/{0}'.format(path)
    return path

def __print_if_not_suppressed(message):
    """Only print to stdout if SUPPRESS_STD_OUT is True. Used to suppress
    messages during unit testing.
    """
    if not SUPPRESS_STD_OUT:
        print(message)

def remove_dev_tag(client, tagUrl):
    """Remove a dev tag from Subversion.
    """
    def log_message():
        return (True, 'TeamCity - delete old dev tag')
    try:
        client.callback_get_log_message = log_message
        __print_if_not_suppressed('Attempting to remove dev tag {0}'.format(tagUrl))
        client.remove(tagUrl)
        __print_if_not_suppressed('Dev tag {0} removed'.format(tagUrl))
    except pysvn.ClientError as ce:
        (msg, error) = ce.args[1][0]
        if error == svnerr.FS_NOT_FOUND:
            __print_if_not_suppressed('Dev tag {0} doesn\'t exist -- moving on'.format(tagUrl))
        else:
            raise

def __get_project_root(trunkUrl):
    """Strip /trunk from the trunk URL and return the first right-parsed partition.
    """
    (rootUrl, _, _) = trunkUrl.rpartition(SVN_SEP)
    return rootUrl

def __get_project_name(rootUrl):
    """Split the root URL to return the project name.
    """
    (_, _, projectName) = rootUrl.rpartition(SVN_SEP)
    return projectName

def __strip_build_number(version):
    """Remove the build number (fouth part) from the version number.
    """
    (ver, _, _) = version.rpartition(VER_SEP)
    return ver

def create_tag(client, name, version, trunk_url, tag_url, tag_source_url):
    """Create a new tag.
    """
    log_message_var = 'TeamCity tagging version {0}, version: {1}'.format(name, version)
    def log_message():
        return (True, log_message_var)
    client.callback_get_log_message = log_message
    try:
        # Check whether it's needed to create the parent
        if not tag_url == tag_source_url:
            client.mkdir(tag_url, log_message_var)
        client.copy(trunk_url, tag_source_url)
        # This line fails on *nix, so the above mkdir and copy is needed. 
        # Of course we're assuming there's only one parent directory. 
        # client.copy2([(trunk_url,)], tag_source_url, make_parents=True)
    except pysvn.ClientError as ce:
        (msg, error) = ce.args[1][0]
        if error == svnerr.FS_ALREADY_EXISTS or error == svnerr.RA_DAV_REQUEST_FAILED:
            __print_if_not_suppressed('Path {0} already exists'.format(tag_source_url))
            return False
        else:
            raise
    return True

def import_artifacts(client, name, version, build_source_full, tag_build_url):
    """Import build artifacts into tag.
    """
    if not os.path.exists(build_source_full):
        __print_if_not_suppressed('Build source {0} for artifacts doesn\'t exist'.format(build_source_full))
        return False
    log_message = 'TeamCity importing build artifacts for {0}, version {1}'.format(name, version)
    revision = client.import_(build_source_full, tag_build_url, log_message)
    __print_if_not_suppressed('Artifacts imported at revision {0}'.format(revision.number))
    return True

def assign_params(svn_info, args, param_dict):
    """Assign parameters from various sources, such as repository information and command-line arguments.

    NOTE: This method modifies param_dict!
    """
    # Setting the EXECUTE_TAGGING_TYPE environment variable must overwrite
    # the command-line paramter T.
    if __env_var_exists(EXECUTE_TAGGING_TYPE):
        if os.getenv(EXECUTE_TAGGING_TYPE) == '':
            param_dict['Tag Type'] = DEFAULT_TAG_TYPE
        else:
            param_dict['Tag Type'] = os.getenv(EXECUTE_TAGGING_TYPE)
        __print_if_not_suppressed('Command-line parameter T={0} overwritten by environment variable EXECUTE_TAGGING_TYPE={1}'.format(args.T, param_dict['Tag Type']))
    else:
        param_dict['Tag Type'] = args.T
    # Normalise (if required) and assign all paths
    param_dict['Source'] = normalise_relative_path(args.S)
    param_dict['Build'] = normalise_relative_path(args.B)
    param_dict['Build Source'] = args.BS
    # Strip build number in case of dev tag
    param_dict['Version'] = args.V
    if is_dev_tag(param_dict['Tag Type']):
        param_dict['Version'] = __strip_build_number(param_dict['Version'])
    # Other URLs and params
    param_dict['Trunk URL'] = svn_info['trunk_url']
    param_dict['Trunk'] = svn_info['trunk_dir']
    param_dict['Build Source Full'] = os.path.join(param_dict['Trunk'], param_dict['Build Source'])
    param_dict['Root URL'] = __get_project_root(param_dict['Trunk URL'])
    param_dict['Name'] = __get_project_name(param_dict['Root URL'])
    param_dict['Tag URL'] = '{0}/tags/{1}-{2}-{3}'.format(param_dict['Root URL'], param_dict['Name'], param_dict['Version'], param_dict['Tag Type'])
    param_dict['Tag Build URL'] = '{0}{1}'.format(param_dict['Tag URL'], param_dict['Build'])
    param_dict['Tag Source URL'] = normalise_url('{0}{1}'.format(param_dict['Tag URL'], param_dict['Source']))

def normalise_url(path):
    """Normalise a URL:
    1. Strip trailing /
    """
    if path.endswith(SVN_SEP):
        return path[:-1]
    return path
