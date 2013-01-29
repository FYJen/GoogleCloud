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

"""Unit tests for the persistent disk snapshot commands."""



import path_initializer
path_initializer.initialize_sys_path()

import copy
import sys

import gflags as flags
import unittest

from gcutil import command_base
from gcutil import mock_api
from gcutil import snapshot_cmds


FLAGS = flags.FLAGS


class SnapshotCmdsTest(unittest.TestCase):

  def _doTestAddSnapshotGeneratesCorrectRequest(self, service_version):
    flag_values = copy.deepcopy(FLAGS)

    command = snapshot_cmds.AddSnapshot('addsnapshot', flag_values)

    expected_project = 'test_project'
    expected_snapshot = 'test_snapshot'
    expected_description = 'test snapshot'
    submitted_source_disk = 'disk1'
    flag_values.service_version = service_version
    flag_values.source_disk = submitted_source_disk
    flag_values.project = expected_project
    flag_values.description = expected_description

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())

    result = command.Handle(expected_snapshot)

    expected_source_disk = command.NormalizeResourceName(
        expected_project,
        'disks',
        submitted_source_disk)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['body']['name'], expected_snapshot)
    self.assertEqual(result['body']['description'], expected_description)
    self.assertEqual(result['body']['sourceDisk'], expected_source_disk)

  def _doTestAddSnapshotFailsWithUnsupportedApiVersion(self, service_version):
    flag_values = copy.deepcopy(FLAGS)

    command = snapshot_cmds.AddSnapshot('addsnapshot', flag_values)

    expected_project = 'test_project'
    expected_snapshot = 'test_snapshot'
    expected_description = 'test snapshot'
    submitted_source_disk = 'disk1'
    flag_values.service_version = service_version
    flag_values.source_disk = submitted_source_disk
    flag_values.project = expected_project
    flag_values.description = expected_description

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    try:
      command.RunWithFlagsAndPositionalArgs(flag_values, [expected_snapshot])
      self.fail('Expected exception')
    except command_base.CommandError:
      pass

  def testAddSnapshotGeneratesCorrectRequest(self):
    first_supported_version = 'v1beta12'
    is_supported = False

    for version in command_base.SUPPORTED_VERSIONS:
      if version == first_supported_version:
        is_supported = True

      if is_supported:
        self._doTestAddSnapshotGeneratesCorrectRequest(version)
      else:
        self._doTestAddSnapshotFailsWithUnsupportedApiVersion(version)

  def testAddSnapshotRequiresSourceDisk(self):
    flag_values = copy.deepcopy(FLAGS)

    command = snapshot_cmds.AddSnapshot('addsnapshot', flag_values)

    expected_project = 'test_project'
    expected_snapshot = 'test_snapshot'
    expected_description = 'test snapshot'
    submitted_version = command_base.CURRENT_VERSION
    submitted_source_disk = 'disk1'

    flag_values.service_version = submitted_version
    flag_values.project = expected_project
    flag_values.description = expected_description

    command.SetFlags(flag_values)

    def GetDiskPath(disk_name):
      disk_path = 'projects/test_project/disks/%s' % (disk_name)
      return disk_path

    disks = {
        'items': [
            {'name': GetDiskPath('disk1')},
            {'name': GetDiskPath('disk2')},
            {'name': GetDiskPath('disk3')}]}

    class MockDisksApi(object):
      def list(self, **unused_kwargs):
        return mock_api.MockRequest(disks)

    api = mock_api.MockApi()
    api.disks = MockDisksApi
    command.SetApi(api)

    expected_disk = command.NormalizeResourceName(
        expected_project,
        'disks',
        submitted_source_disk)

    mock_output = mock_api.MockOutput()
    mock_input = mock_api.MockInput('1\n\r')
    oldin = sys.stdin
    sys.stdin = mock_input
    oldout = sys.stdout
    sys.stdout = mock_output

    result = command.Handle(expected_snapshot)
    self.assertEqual(result['body']['sourceDisk'], expected_disk)
    sys.stdin = oldin
    sys.stdout = oldout

  def testGetSnapshotGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = snapshot_cmds.GetSnapshot('getsnapshot', flag_values)

    expected_project = 'test_project'
    expected_snapshot = 'test_snapshot'
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())

    result = command.Handle(expected_snapshot)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['snapshot'], expected_snapshot)

  def testDeleteSnapshotGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = snapshot_cmds.DeleteSnapshot('deletesnapshot', flag_values)

    expected_project = 'test_project'
    expected_snapshot = 'test_snapshot'
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(expected_snapshot)
    self.assertEquals(exceptions, [])
    self.assertEquals(len(results['items']), 1)
    result = results['items'][0]

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['snapshot'], expected_snapshot)

  def testDeleteMultipleSnapshots(self):
    flag_values = copy.deepcopy(FLAGS)
    command = snapshot_cmds.DeleteSnapshot('deletesnapshot', flag_values)

    expected_project = 'test_project'
    expected_snapshots = ['test-snapshot-%02d' % x for x in xrange(100)]
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(*expected_snapshots)
    self.assertEqual(exceptions, [])
    results = results['items']
    self.assertEqual(len(results), len(expected_snapshots))

    for expected_snapshot, result in zip(expected_snapshots, results):
      self.assertEqual(result['project'], expected_project)
      self.assertEqual(result['snapshot'], expected_snapshot)

  def testListSnapshotsGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = snapshot_cmds.ListSnapshots('listsnapshots', flag_values)

    expected_project = 'test_project'
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())

    result = command.Handle()

    self.assertEqual(result['project'], expected_project)


if __name__ == '__main__':
  unittest.main()
