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

"""Unit tests for the persistent disk commands."""



import path_initializer
path_initializer.initialize_sys_path()

import copy
import sys

import gflags as flags
import unittest

from gcutil import command_base
from gcutil import disk_cmds
from gcutil import mock_api


FLAGS = flags.FLAGS


class DiskCmdsTest(unittest.TestCase):

  def _doTestAddDiskGeneratesCorrectRequest(self, service_version):
    flag_values = copy.deepcopy(FLAGS)

    command = disk_cmds.AddDisk('adddisk', flag_values)

    expected_project = 'test_project'
    expected_disk = 'test_disk'
    expected_description = 'test disk'
    submitted_zone = 'copernicus-moon-base'
    expected_size = 20
    flag_values.service_version = service_version
    flag_values.zone = submitted_zone
    flag_values.project = expected_project
    flag_values.size_gb = expected_size
    flag_values.description = expected_description

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(expected_disk)
    self.assertEqual(len(results['items']), 1)
    self.assertEqual(exceptions, [])
    result = results['items'][0]

    expected_zone = command.NormalizeResourceName(
        expected_project,
        'zones',
        submitted_zone)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['body']['name'], expected_disk)
    self.assertEqual(result['body']['description'], expected_description)
    self.assertEqual(result['body']['sizeGb'], expected_size)
    self.assertEqual(result['body']['zone'], expected_zone)

  def testAddDiskGeneratesCorrectRequest(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._doTestAddDiskGeneratesCorrectRequest(version)

  def _doTestAddMultipleDisks(self, service_version):
    flag_values = copy.deepcopy(FLAGS)
    command = disk_cmds.AddDisk('adddisk', flag_values)

    expected_kind = command._GetResourceApiKind('disk')
    expected_project = 'test_project'
    expected_disks = ['test-disk-%02d' % i for i in xrange(100)]
    expected_description = 'test disk'
    submitted_zone = 'copernicus-moon-base'
    expected_size = 12

    flag_values.service_version = service_version
    flag_values.zone = submitted_zone
    flag_values.project = expected_project
    flag_values.size_gb = expected_size
    flag_values.description = expected_description

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    expected_zone = command.NormalizeResourceName(
        expected_project, 'zones', submitted_zone)

    results, exceptions = command.Handle(*expected_disks)
    self.assertEqual(exceptions, [])
    results = results['items']
    self.assertEqual(len(results), len(expected_disks))

    for expected_disk, result in zip(expected_disks, results):
      self.assertEqual(result['project'], expected_project)
      self.assertEqual(result['body']['kind'], expected_kind)
      self.assertEqual(result['body']['sizeGb'], expected_size)
      self.assertEqual(result['body']['name'], expected_disk)
      self.assertEqual(result['body']['zone'], expected_zone)
      self.assertEqual(result['body']['description'], expected_description)

  def testAddMultipleDisks(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._doTestAddMultipleDisks(version)


  def testAddDiskDefaultSizeGb(self):
    flag_values = copy.deepcopy(FLAGS)

    command = disk_cmds.AddDisk('adddisk', flag_values)

    flag_values.zone = 'copernicus-moon-base'
    flag_values.project = 'test_project'

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle('disk1')
    self.assertEqual(len(results['items']), 1)
    self.assertEqual(exceptions, [])
    result = results['items'][0]

    # We did not set the size, make sure it defaults to 10GB.
    self.assertEqual(10, result['body']['sizeGb'])


  def testAddDiskRequiresSharedFateZone(self):
    flag_values = copy.deepcopy(FLAGS)

    command = disk_cmds.AddDisk('adddisk', flag_values)

    expected_project = 'test_project'
    expected_disk = 'test_disk'
    expected_description = 'test disk'
    expected_size = 20
    submitted_version = command_base.CURRENT_VERSION
    submitted_zone = 'us-east-a'

    flag_values.service_version = submitted_version
    flag_values.project = expected_project
    flag_values.size_gb = expected_size
    flag_values.description = expected_description

    command.SetFlags(flag_values)

    def GetZonePath(part_one, part_two, part_three):
      zone_path = 'projects/test_project/zones/%s-%s-%s' % (
          part_one, part_two, part_three)

      return zone_path

    zones = {
        'items': [
            {'name': GetZonePath('us', 'east', 'a')},
            {'name': GetZonePath('us', 'east', 'b')},
            {'name': GetZonePath('us', 'east', 'c')},
            {'name': GetZonePath('us', 'west', 'a')}]}

    class MockSharedFateZonesApi(object):
      def list(self, **unused_kwargs):
        return mock_api.MockRequest(zones)

    class MockZonesApi(object):
      def list(self, **unused_kwargs):
        return mock_api.MockRequest(zones)

    api = mock_api.MockApi()
    api.sharedFateZones = MockSharedFateZonesApi
    api.zones = MockZonesApi
    command.SetApi(api)
    command._credential = mock_api.MockCredential()

    expected_zone = command.NormalizeResourceName(
        expected_project,
        'zones',
        submitted_zone)

    mock_output = mock_api.MockOutput()
    mock_input = mock_api.MockInput('1\n\r')
    oldin = sys.stdin
    sys.stdin = mock_input
    oldout = sys.stdout
    sys.stdout = mock_output

    results, exceptions = command.Handle(expected_disk)
    self.assertEqual(len(results['items']), 1)
    self.assertEqual(exceptions, [])
    result = results['items'][0]
    self.assertEqual(result['body']['zone'], expected_zone)
    sys.stdin = oldin
    sys.stdout = oldout

  def testGetDiskGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = disk_cmds.GetDisk('getdisk', flag_values)

    expected_project = 'test_project'
    expected_disk = 'test_disk'
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    result = command.Handle(expected_disk)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['disk'], expected_disk)

  def testDeleteDiskGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = disk_cmds.DeleteDisk('deletedisk', flag_values)

    expected_project = 'test_project'
    expected_disk = 'test_disk'
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(expected_disk)
    self.assertEqual(len(results['items']), 1)
    self.assertEqual(exceptions, [])
    result = results['items'][0]

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['disk'], expected_disk)

  def testDeleteMultipleDisks(self):
    flag_values = copy.deepcopy(FLAGS)
    command = disk_cmds.DeleteDisk('deletedisk', flag_values)

    expected_project = 'test_project'
    expected_disks = ['test-disk-%02d' % x for x in xrange(100)]
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(*expected_disks)
    self.assertEqual(exceptions, [])
    results = results['items']
    self.assertEqual(len(results), len(expected_disks))

    for expected_disk, result in zip(expected_disks, results):
      self.assertEqual(result['project'], expected_project)
      self.assertEqual(result['disk'], expected_disk)

  def testListDisksGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = disk_cmds.ListDisks('listdisks', flag_values)

    expected_project = 'test_project'
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    result = command.Handle()

    self.assertEqual(result['project'], expected_project)


if __name__ == '__main__':
  unittest.main()
