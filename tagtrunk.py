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

try:
    import os
    import traceback
    import tagutils
except Exception as ex:
    print('One or more classes or modules could not be imported: {0}'.format(ex))
    exit(1)

def main():
    """ Standalone Python script used by TeamCity to automate the tagging of a project.

    Exit codes:
    0 - normal termination
    1 - other errors
    2 - syntax error
    """

    # Subversion server account credentials
    # TODO: Implement a ConfigParser
    __SVN_USERNAME = 'teamcity'
    __SVN_PASSWORD = 'Password123'

    try:
        # Get command-line parameters
        parser = tagutils.setup_argument_parser()
        args = parser.parse_args()

        # Check command-line arguments
        (valid, errorMessage) = tagutils.validate_args(args)
        if not valid:
            tagutils.print_teamcity_error_message(errorMessage)
            exit(1)

        # Store all parameters in a dictionary
        param_dict = {}

        # Get repository information
        client = tagutils.setup_svn_client(__SVN_USERNAME, __SVN_PASSWORD)
        info = tagutils.get_repository_info(client, os.getcwd())
        if info is None:
            tagutils.print_teamcity_error_message('Could not get repository info')
            exit(1)

        # Construct and assign all required parameters
        tagutils.assign_params(info, args, param_dict)
        tagutils.print_script_parameters(param_dict)

        # Dev tag excludes build digit so that it can be deleted easily
        if tagutils.is_dev_tag(param_dict['Tag Type']):
            tagutils.remove_dev_tag(client, param_dict['Tag URL'])
        if not tagutils.create_tag(client,
                                   param_dict['Name'],
                                   param_dict['Version'],
                                   param_dict['Trunk URL'],
                                   param_dict['Tag URL'],
                                   param_dict['Tag Source URL']):
            tagutils.print_teamcity_error_message('Could not create tag')
            exit(1)
        if not tagutils.import_artifacts(client,
                                         param_dict['Name'],
                                         param_dict['Version'],
                                         param_dict['Build Source Full'],
                                         param_dict['Tag Build URL']):
            tagutils.print_teamcity_error_message('Could not import build artifacts')
            exit(1)
        tagutils.print_teamcity_info_message('Tagging process succeeded')
        exit(0)

    except Exception as ex:
        print('An unexpected error occurred')
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
