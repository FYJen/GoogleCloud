#!/usr/bin/python
#
# Copyright 2012 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""An simple utilites for use with Google Compute Engine library."""

import collections
import ConfigParser
import datetime
import json
import os
import urllib


import oauth2client.client
import oauth2client.file
import oauth2client.tools
import gflags

gflags.FLAGS.auth_local_webserver = False

# Credential and configuration files.
GCE_CREDENTIALS_FILE = '~/.gce.credentials'
DEFAULT_GCE_CONFIG_FILE = '~/.gce.config'

# Config file section name.
GCE_CONFIG_SECTION = 'gce_config'


GceDefaults = collections.namedtuple(
    'GceDefaults', ('project', 'image', 'machine_type', 'network', 'zone'))


def get_credentials():
  """Returns OAuth2 credentials for use with Google Compute Engine Api.

  Loads the credentials from the credentials file. If the credentials are
  missing or invalid, performs the OAuth2 authentication flow.

  Returns:
    oauth2client credentials object to use with the GoogleComputeEngine Api.
  """
  storage = oauth2client.file.Storage(os.path.expanduser(GCE_CREDENTIALS_FILE))
  credentials = storage.get()


  if credentials is None or credentials.invalid:
    flow = oauth2client.client.OAuth2WebServerFlow(
        client_id=('1025389682001-n2ls6kecqj0ftjfusf4olblksm5glm2o'
                   '.apps.googleusercontent.com'),
        client_secret='F8xOGQrZU-htG_wyByTKuQ61',
        scope='https://www.googleapis.com/auth/compute',
        user_agent='google-compute-engine-demo/0.1')
    credentials = oauth2client.tools.run(flow, storage)
  return credentials


class ServiceAccountCredentials(oauth2client.client.OAuth2Credentials):
  """Credentials object that uses service account scopes inside an instance."""

  def __init__(self, scopes='https://www.googleapis.com/auth/compute'):
    self.scopes = scopes
    access_token, token_expiry = self._internal_refresh()
    oauth2client.client.OAuth2Credentials.__init__(self, access_token, None,
                                                   None, None, token_expiry,
                                                   None, None)

  def _refresh(self, _):
    self.access_token, self.token_expiry = self._internal_refresh()

  def _internal_refresh(self):
    url = ('http://metadata/0.1/meta-data/service-accounts/default/'
           'acquire?scopes=' + self.scopes)
    data = json.loads(urllib.urlopen(url).read())
    return (data['accessToken'],
            datetime.datetime.utcfromtimestamp(data['expiresAt']))


def get_defaults(config_file=DEFAULT_GCE_CONFIG_FILE):
  """Loads the default values to use with the GoogleComputeEngine API.

  The default values are loaded from the configuration file.

  Args:
    config_file: The path to the configuration file.

  Returns:
    The GceDefaults named tuple with the default values.
  """

  def get_option(cfg, option, default=None):
    if cfg.has_option(GCE_CONFIG_SECTION, option):
      return cfg.get(GCE_CONFIG_SECTION, option)
    return default

  config = ConfigParser.RawConfigParser()
  config.read(os.path.expanduser(config_file))
  return GceDefaults(
      get_option(config, 'project'),
      get_option(config, 'image'),
      get_option(config, 'machine_type'),
      get_option(config, 'network', 'default'),
      get_option(config, 'zone'))


def build_config(api):
  """Creates a new configuration file.

  The process is interactive: it requires input from the user from standard in.

  Args:
    api: An instance of GoogleComputeEngine that can be used to query images,
      zones, the user's projects, etc...

  Returns:
    The location to which the configuration file should be saved.
  """

  def choose(iterable, name):
    """Prompts the user to choose an item from the elements of the iterable."""
    items = sorted(iterable, key=lambda i: i.name)
    choices = [str(i) for i in range(1, len(items) + 1)]
    i = 1
    for item in items:
      print '{0}: {1}'.format(i, item.name)
      i += 1
    while True:
      choice = raw_input('Which of the {0} above do you want as your default? '
                         .format(name))
      if choice in choices:
        break
      else:
        print 'Oops! Please select one of [{0}].'.format(' '.join(choices))
    return items[int(choice) - 1].name

  print 'I\'m going to help you create a new configuration file.'
  print 'If you get tired of me, hit EOF and I will go away nicely.'

  try:
    config_file = raw_input(
        'Choose a location for the config file (enter nothing for {0}): '
        .format(DEFAULT_GCE_CONFIG_FILE))
    config_file = config_file or DEFAULT_GCE_CONFIG_FILE

    while True:
      project = raw_input('What is the name of your project? ')
      try:
        api.get_project(project=project)
        break
      except ValueError:
        print 'Oops! I couldn\'t find your project. Try again!'

    image = choose(api.all_images(project='google'), 'images')
    machine_type = choose(api.all_machine_types(project=project),
                          'machine types')
    zone = choose(api.all_zones(project=project), 'zones')
  except EOFError:
    print
    print ('Perhaps we can try creating your configuration file some other '
           'time.')
    return None

  # Writes the configuration to the config file.
  config = ConfigParser.RawConfigParser()
  config.add_section(GCE_CONFIG_SECTION)
  config.set(GCE_CONFIG_SECTION, 'project', project)
  config.set(GCE_CONFIG_SECTION, 'image', 'projects/google/images/' + image)
  config.set(GCE_CONFIG_SECTION, 'machine_type', machine_type)
  config.set(GCE_CONFIG_SECTION, 'zone', zone)
  with open(os.path.expanduser(config_file), 'w') as f:
    config.write(f)

  print 'Your configuration has been saved to {0}.'.format(config_file)
  print 'Feel free to edit the file or re-run config() in the future.'

  return config_file
