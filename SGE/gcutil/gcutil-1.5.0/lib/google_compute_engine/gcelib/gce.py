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

"""Contains a factory function for constructing GoogleComputeEngine objects.

This module also defines GceError, the exception that can be raised
when interacting with the service.
"""

import logging

VERSIONS = ('v1beta12', 'v1beta13')
DEFAULT_VERSION = 'v1beta13'


class GceError(Exception):
  """The error that can be raised when problems arise.

  Clients can use the details attribute to see more details about the
  error.
  """

  def __init__(self, message=None, status=None):
    super(GceError, self).__init__()
    assert message or status, (
        'At least one of message and status must be present.')
    self.message = message
    self.status = status

  def __str__(self):
    if not self.message:
      return 'Received status code {0} from server.'.format(self.status)
    if not self.status:
      return self.message
    return 'Received status code {0}: {1}'.format(self.status, self.message)

  def __repr__(self):
    return '{0}(message={1}, status={2})'.format(
        self.__class__.__name__, repr(self.message), repr(self.status))

  def __nonzero__(self):
    return False

  def __eq__(self, other):
    return (isinstance(other, self.__class__) and
            self.message == other.message and
            self.status == other.status)


def get_api(
    credentials,
    logging_level=logging.WARN,
    base_url=None,
    default_image=None,
    default_machine_type=None,
    default_network='default',
    default_network_interface=None,
    default_project=None,
    default_zone=None,
    version=DEFAULT_VERSION,
    trace_token=None):
  """Returns a new GoogleComputeEngine object based on the given version."""

  if version not in VERSIONS:
    raise ValueError('Could not recognize given version: {0}'.format(version))

  gce_library = __import__('gce_' + version, globals(), locals(), [], -1)
  return gce_library.GoogleComputeEngine(
      credentials=credentials,
      logging_level=logging_level,
      base_url=base_url,
      default_image=default_image,
      default_machine_type=default_machine_type,
      default_network=default_network,
      default_network_interface=default_network_interface,
      default_project=default_project,
      default_zone=default_zone,
      trace_token=trace_token)
