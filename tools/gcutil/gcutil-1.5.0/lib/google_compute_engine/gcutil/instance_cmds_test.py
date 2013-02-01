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

"""Unit tests for the instance commands."""

from __future__ import with_statement



import path_initializer
path_initializer.initialize_sys_path()

import base64
import copy
import logging
import sys
import tempfile

from google.apputils import app
import gflags as flags
import unittest

from gcutil import command_base
from gcutil import gcutil_logging
from gcutil import instance_cmds
from gcutil import mock_api


FLAGS = flags.FLAGS
LOGGER = gcutil_logging.LOGGER


class InstanceCmdsTest(unittest.TestCase):

  def setUp(self):
    self._projects = mock_api.MockProjectsApi()
    self._instances = mock_api.MockInstancesApi()
    self._machine_types = mock_api.MockMachineTypesApi()
    self._zones = mock_api.MockZonesApi()
    self._disks = mock_api.MockDisksApi()
    self._images = mock_api.MockImagesApi()

    self._projects.get = mock_api.CommandExecutor(
        {'externalIpAddresses': ['192.0.2.2', '192.0.2.3', '192.0.2.4']})

    # This response is used for 'instances.list' on certain add calls.
    self._instance_list = {
        'items': [
            {'name': 'foo',
             'networkInterfaces': [{'accessConfigs': [{'type': 'ONE_TO_ONE_NAT',
                                                       'natIP': '192.0.2.2'}]}]
            },
            {'name': 'bar',
             'networkInterfaces': [{'accessConfigs': [{'type': 'ONE_TO_ONE_NAT',
                                                       'natIP': '192.0.2.3'}]}]
            },
            ]}

  def _doTestAddInstanceGeneratesCorrectRequest(self, service_version):
    flag_values = copy.deepcopy(FLAGS)

    command = instance_cmds.AddInstance('addinstance', flag_values)

    expected_project = 'test_project'
    expected_instance = 'test_instance'
    expected_description = 'test instance'
    submitted_image = 'expected_image'
    submitted_machine_type = 'goes_to_11'
    submitted_zone = 'copernicus-moon-base'

    expected_authorized_ssh_keys = []
    flag_values.service_version = service_version
    flag_values.zone = submitted_zone
    flag_values.machine_type = submitted_machine_type
    flag_values.project = expected_project
    flag_values.description = expected_description
    flag_values.image = submitted_image
    flag_values.use_compute_key = False
    flag_values.authorized_ssh_keys = expected_authorized_ssh_keys
    flag_values.add_compute_key_to_project = False

    self._instances.list = mock_api.CommandExecutor(self._instance_list)

    command.SetFlags(flag_values)
    command._projects_api = self._projects
    command._instances_api = self._instances
    command._zones_api = self._zones
    command._credential = mock_api.MockCredential()

    expected_image = command.NormalizeResourceName(expected_project,
                                                   'images',
                                                   submitted_image)

    expected_zone = command.NormalizeResourceName(
        expected_project,
        'zones',
        submitted_zone)

    (results, exceptions) = command.Handle(expected_instance)
    result = results['items'][0]

    expected_kind = command._GetResourceApiKind('instance')

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['body']['kind'], expected_kind)
    self.assertEqual(result['body']['name'], expected_instance)
    self.assertEqual(result['body']['description'], expected_description)
    self.assertEqual(result['body']['image'], expected_image)
    self.assertFalse(
        'natIP' in result['body']['networkInterfaces'][0]['accessConfigs'][0],
        result)
    self.assertEqual(result['body']['zone'], expected_zone)
    self.assertEqual(exceptions, [])

    self.assertEqual(result['body'].get('metadata'), {
        'kind': 'compute#metadata',
        'items': []})

    self.assertEqual(result['body'].get('tags', []), [])

  def testAddInstanceGeneratesCorrectRequest(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._doTestAddInstanceGeneratesCorrectRequest(version)

  def _doTestAddMultipleInstances(self, service_version):
    flag_values = copy.deepcopy(FLAGS)

    command = instance_cmds.AddInstance('addinstance', flag_values)

    expected_project = 'test_project'
    expected_instances = ['test-instance-%02d' % i for i in xrange(100)]
    expected_description = 'test instance'
    submitted_image = 'expected_image'
    submitted_machine_type = 'goes_to_11'
    submitted_zone = 'copernicus-moon-base'

    expected_authorized_ssh_keys = []
    flag_values.service_version = service_version
    flag_values.zone = submitted_zone
    flag_values.machine_type = submitted_machine_type
    flag_values.project = expected_project
    flag_values.description = expected_description
    flag_values.image = submitted_image
    flag_values.use_compute_key = False
    flag_values.authorized_ssh_keys = expected_authorized_ssh_keys
    flag_values.add_compute_key_to_project = False

    self._instances.list = mock_api.CommandExecutor(self._instance_list)

    command.SetFlags(flag_values)
    command._projects_api = self._projects
    command._instances_api = self._instances
    command._zones_api = self._zones
    command._credential = mock_api.MockCredential()

    expected_image = command.NormalizeResourceName(expected_project,
                                                   'images',
                                                   submitted_image)

    expected_zone = command.NormalizeResourceName(
        expected_project,
        'zones',
        submitted_zone)

    (results, exceptions) = command.Handle(*expected_instances)

    self.assertEqual(exceptions, [])
    results = results['items']
    self.assertEqual(len(results), len(expected_instances))

    for (expected_instance, result) in zip(expected_instances, results):
      expected_kind = command._GetResourceApiKind('instance')

      self.assertEqual(result['project'], expected_project)
      self.assertEqual(result['body']['kind'], expected_kind)
      self.assertEqual(result['body']['name'], expected_instance)
      self.assertEqual(result['body']['description'], expected_description)
      self.assertEqual(result['body']['image'], expected_image)
      self.assertFalse(
          'natIP' in result['body']['networkInterfaces'][0]['accessConfigs'][0],
          result)
      self.assertEqual(result['body']['zone'], expected_zone)

      self.assertEqual(result['body'].get('metadata'), {
          'kind': 'compute#metadata',
          'items': []})

      self.assertEqual(result['body'].get('tags', []), [])

  def testAddMultipleInstances(self):
    for version in command_base.SUPPORTED_VERSIONS:
      self._doTestAddMultipleInstances(version)


  def testAddInstanceWithDiskOptionsGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = instance_cmds.AddInstance('addinstance', flag_values)

    service_version = command_base.CURRENT_VERSION
    expected_instance = 'test_instance'
    submitted_disk_old_name = 'disk123:name123'
    submitted_disk_name = 'disk234,deviceName=name234'
    submitted_disk_read_only = 'disk345,mode=READ_ONLY'
    submitted_disk_read_write = 'disk456,mode=READ_WRITE'
    submitted_disk_name_read_only = 'disk567,deviceName=name567,mode=READ_ONLY'
    submitted_disk_no_name = 'disk678'
    submitted_disk_full_name = ('http://www.googleapis.com/compute/v1beta12/'
                                'projects/google.com:test/disks/disk789')
    submitted_disk_ro = 'disk890,mode=ro'
    submitted_disk_rw = 'disk90A,mode=rw'
    submitted_machine_type = 'goes_to_11'

    expected_authorized_ssh_keys = []
    flag_values.service_version = service_version

    flag_values.disk = [submitted_disk_old_name,
                        submitted_disk_name,
                        submitted_disk_read_only,
                        submitted_disk_read_write,
                        submitted_disk_name_read_only,
                        submitted_disk_no_name,
                        submitted_disk_full_name + ',mode=READ_WRITE',
                        submitted_disk_ro,
                        submitted_disk_rw]
    flag_values.machine_type = submitted_machine_type
    flag_values.use_compute_key = False
    flag_values.authorized_ssh_keys = expected_authorized_ssh_keys
    flag_values.add_compute_key_to_project = False

    disk_zone = 'zones/copernicus-moon-base'

    self._disks.get = mock_api.CommandExecutor(
        {'zone': disk_zone})
    self._instances.list = mock_api.CommandExecutor(self._instance_list)

    command.SetFlags(flag_values)
    command._projects_api = self._projects
    command._instances_api = self._instances
    command._disks_api = self._disks
    command._zones_api = self._zones
    command._credential = mock_api.MockCredential()

    (results, exceptions) = command.Handle(expected_instance)
    result = results['items'][0]

    disk = result['body']['disks'][0]
    self.assertEqual(disk['deviceName'], 'name123')
    self.assertEqual(disk['mode'], 'READ_WRITE')
    disk = result['body']['disks'][1]
    self.assertEqual(disk['deviceName'], 'name234')
    self.assertEqual(disk['mode'], 'READ_WRITE')
    disk = result['body']['disks'][2]
    self.assertEqual(disk['deviceName'], 'disk345')
    self.assertEqual(disk['mode'], 'READ_ONLY')
    disk = result['body']['disks'][3]
    self.assertEqual(disk['deviceName'], 'disk456')
    self.assertEqual(disk['mode'], 'READ_WRITE')
    disk = result['body']['disks'][4]
    self.assertEqual(disk['deviceName'], 'name567')
    self.assertEqual(disk['mode'], 'READ_ONLY')
    disk = result['body']['disks'][5]
    self.assertEqual(disk['deviceName'], submitted_disk_no_name)
    self.assertEqual(disk['mode'], 'READ_WRITE')
    disk = result['body']['disks'][6]
    self.assertEqual(disk['deviceName'], submitted_disk_full_name)
    self.assertEqual(disk['mode'], 'READ_WRITE')
    disk = result['body']['disks'][7]
    self.assertEqual(disk['deviceName'], 'disk890')
    self.assertEqual(disk['mode'], 'READ_ONLY')
    disk = result['body']['disks'][8]
    self.assertEqual(disk['deviceName'], 'disk90A')
    self.assertEqual(disk['mode'], 'READ_WRITE')
    self.assertEqual(exceptions, [])


  def testAddInstanceWithDiskGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = instance_cmds.AddInstance('addinstance', flag_values)
    service_version = command_base.CURRENT_VERSION

    expected_project = 'test_project'
    expected_instance = 'test_instance'
    expected_description = 'test instance'
    submitted_image = 'expected_image'
    submitted_disk = 'disk123'
    submitted_machine_type = 'goes_to_11'
    submitted_zone = 'copernicus-moon-base'

    expected_authorized_ssh_keys = []
    flag_values.service_version = service_version
    flag_values.disk = [submitted_disk]
    flag_values.project = expected_project
    flag_values.description = expected_description
    flag_values.image = submitted_image
    flag_values.machine_type = submitted_machine_type
    flag_values.use_compute_key = False
    flag_values.authorized_ssh_keys = expected_authorized_ssh_keys
    flag_values.add_compute_key_to_project = False

    self._instances.list = mock_api.CommandExecutor(self._instance_list)

    command.SetFlags(flag_values)
    command._projects_api = self._projects
    command._instances_api = self._instances
    command._disks_api = self._disks
    command._zones_api = self._zones
    command._credential = mock_api.MockCredential()

    zone_path = 'projects/test_project/zones/%s' % submitted_zone
    self._disks.get = mock_api.CommandExecutor(
        {'zone': zone_path})

    expected_metadata = {'kind': 'compute#metadata',
                         'items': []}

    expected_image = command.NormalizeResourceName(expected_project,
                                                   'images',
                                                   submitted_image)

    expected_disk = command.NormalizeResourceName(expected_project,
                                                  'disks',
                                                  submitted_disk)

    expected_zone = command.NormalizeResourceName(
        expected_project,
        'zones',
        submitted_zone)

    (results, exceptions) = command.Handle(expected_instance)
    result = results['items'][0]

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['body']['name'], expected_instance)
    self.assertEqual(result['body']['description'], expected_description)
    self.assertEqual(result['body']['image'], expected_image)
    self.assertEqual(result['body']['disks'][0]['source'], expected_disk)
    self.assertFalse(
        'natIP' in result['body']['networkInterfaces'][0]['accessConfigs'][0],
        result)
    self.assertEqual(result['body']['zone'], expected_zone)
    self.assertEqual(result['body'].get('metadata', {}), expected_metadata)
    self.assertEqual(result['body'].get('tags', []), [])
    self.assertEqual(exceptions, [])

  def testAddInstanceGeneratesEphemeralIpRequestForProjectWithNoIps(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.AddInstance('addinstance', flag_values)

    service_version = command_base.CURRENT_VERSION
    expected_project = 'test_project'
    expected_instance = 'test_instance'
    expected_description = 'test instance'
    submitted_image = 'expected_image'
    submitted_machine_type = 'goes_to_11'
    submitted_zone = 'copernicus-moon-base'

    expected_authorized_ssh_keys = []
    flag_values.service_version = service_version
    flag_values.zone = submitted_zone
    flag_values.project = expected_project
    flag_values.description = expected_description
    flag_values.image = submitted_image
    flag_values.machine_type = submitted_machine_type
    flag_values.use_compute_key = False
    flag_values.authorized_ssh_keys = expected_authorized_ssh_keys
    flag_values.add_compute_key_to_project = False

    self._projects.get = mock_api.CommandExecutor(
        {'externalIpAddresses': []})
    self._instances.list = mock_api.CommandExecutor({'items': []})

    command.SetFlags(flag_values)
    command._projects_api = self._projects
    command._instances_api = self._instances
    command._zones_api = self._zones
    command._credential = mock_api.MockCredential()

    expected_metadata = {'kind': 'compute#metadata',
                         'items': []}

    expected_image = command.NormalizeResourceName(expected_project,
                                                   'images',
                                                   submitted_image)

    expected_zone = command.NormalizeResourceName(
        expected_project,
        'zones',
        submitted_zone)

    (results, exceptions) = command.Handle(expected_instance)
    result = results['items'][0]

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['body']['name'], expected_instance)
    self.assertEqual(result['body']['description'], expected_description)
    self.assertEqual(result['body']['image'], expected_image)
    self.assertFalse('natIP' in
                     result['body']['networkInterfaces'][0]['accessConfigs'][0],
                     result)
    self.assertEqual(result['body']['zone'], expected_zone)
    self.assertEqual(result['body'].get('metadata'), expected_metadata)
    self.assertEqual(result['body'].get('tags', []), [])
    self.assertEqual(exceptions, [])

  def testAddInstanceNoExistingVmsRequest(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.AddInstance('addinstance', flag_values)

    service_version = command_base.CURRENT_VERSION
    expected_project = 'test_project'
    expected_instance = 'test_instance'
    expected_description = 'test instance'
    submitted_image = 'expected_image'
    submitted_machine_type = 'goes_to_11'
    submitted_zone = 'copernicus-moon-base'

    expected_authorized_ssh_keys = []
    flag_values.service_version = service_version
    flag_values.zone = submitted_zone
    flag_values.project = expected_project
    flag_values.description = expected_description
    flag_values.image = submitted_image
    flag_values.machine_type = submitted_machine_type
    flag_values.use_compute_key = False
    flag_values.authorized_ssh_keys = expected_authorized_ssh_keys
    flag_values.add_compute_key_to_project = False

    self._projects.get = mock_api.CommandExecutor(
        {'externalIpAddresses': ['192.0.2.2', '192.0.2.3']})
    self._instances.list = mock_api.CommandExecutor(
        {'kind': 'cloud#instances'})

    command.SetFlags(flag_values)
    command._projects_api = self._projects
    command._instances_api = self._instances
    command._zones_api = self._zones
    command._credential = mock_api.MockCredential()

    expected_metadata = {'kind': 'compute#metadata',
                         'items': []}

    expected_image = command.NormalizeResourceName(expected_project,
                                                   'images',
                                                   submitted_image)

    expected_zone = command.NormalizeResourceName(
        expected_project,
        'zones',
        submitted_zone)

    (results, exceptions) = command.Handle(expected_instance)
    result = results['items'][0]

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['body']['name'], expected_instance)
    self.assertEqual(result['body']['description'], expected_description)
    self.assertEqual(result['body']['image'], expected_image)
    self.assertFalse(
        'natIP' in result['body']['networkInterfaces'][0]['accessConfigs'][0],
        result)
    self.assertEqual(result['body']['zone'], expected_zone)
    self.assertEqual(result['body'].get('metadata'), expected_metadata)
    self.assertEqual(result['body'].get('tags', []), [])
    self.assertEqual(exceptions, [])

  def testAddInstanceWithSpecifiedInternalAddress(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.AddInstance('addinstance', flag_values)
    service_version = command_base.CURRENT_VERSION
    expected_project = 'test_project'
    expected_instance = 'test_instance'
    expected_description = 'test instance'
    submitted_image = 'expected_image'
    submitted_machine_type = 'goes_to_11'
    submitted_zone = 'copernicus-moon-base'

    expected_authorized_ssh_keys = []
    expected_internal_ip = '10.0.0.1'
    flag_values.service_version = service_version
    flag_values.zone = submitted_zone
    flag_values.project = expected_project
    flag_values.description = expected_description
    flag_values.image = submitted_image
    flag_values.internal_ip_address = expected_internal_ip
    flag_values.machine_type = submitted_machine_type
    flag_values.use_compute_key = False
    flag_values.authorized_ssh_keys = expected_authorized_ssh_keys
    flag_values.add_compute_key_to_project = False

    self._instances.list = mock_api.CommandExecutor(self._instance_list)

    command.SetFlags(flag_values)
    command._projects_api = self._projects
    command._instances_api = self._instances
    command._zones_api = self._zones
    command._credential = mock_api.MockCredential()

    expected_metadata = {'kind': 'compute#metadata',
                         'items': []}

    expected_image = command.NormalizeResourceName(expected_project,
                                                   'images',
                                                   submitted_image)

    expected_zone = command.NormalizeResourceName(
        expected_project,
        'zones',
        submitted_zone)

    (results, exceptions) = command.Handle(expected_instance)
    result = results['items'][0]

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['body']['name'], expected_instance)
    self.assertEqual(result['body']['description'], expected_description)
    self.assertEqual(result['body']['image'], expected_image)
    self.assertEqual(result['body']['networkInterfaces'][0]['networkIP'],
                     expected_internal_ip)
    self.assertEqual(result['body']['zone'], expected_zone)
    self.assertEqual(result['body'].get('metadata'), expected_metadata)
    self.assertEqual(result['body'].get('tags', []), [])
    self.assertEqual(exceptions, [])

  def testAddInstanceGeneratesNewIpRequest(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.AddInstance('addinstance', flag_values)

    service_version = command_base.CURRENT_VERSION
    expected_project = 'test_project'
    expected_instance = 'test_instance'
    expected_description = 'test instance'
    submitted_image = 'expected_image'
    submitted_machine_type = 'goes_to_11'
    submitted_zone = 'copernicus-moon-base'

    expected_authorized_ssh_keys = []
    flag_values.service_version = service_version
    flag_values.zone = submitted_zone
    flag_values.project = expected_project
    flag_values.description = expected_description
    flag_values.image = submitted_image
    flag_values.external_ip_address = 'ephemeral'
    flag_values.machine_type = submitted_machine_type
    flag_values.use_compute_key = False
    flag_values.authorized_ssh_keys = expected_authorized_ssh_keys
    flag_values.add_compute_key_to_project = False

    self._instances.list = mock_api.CommandExecutor(self._instance_list)

    command.SetFlags(flag_values)
    command._projects_api = self._projects
    command._instances_api = self._instances
    command._zones_api = self._zones
    command._credential = mock_api.MockCredential()

    expected_metadata = {'kind': 'compute#metadata',
                         'items': []}

    expected_image = command.NormalizeResourceName(expected_project,
                                                   'images',
                                                   submitted_image)

    expected_zone = command.NormalizeResourceName(
        expected_project,
        'zones',
        submitted_zone)

    (results, exceptions) = command.Handle(expected_instance)
    result = results['items'][0]

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['body']['name'], expected_instance)
    self.assertEqual(result['body']['description'], expected_description)
    self.assertEqual(result['body']['image'], expected_image)
    self.assertFalse('natIP' in
                     result['body']['networkInterfaces'][0]['accessConfigs'][0])
    self.assertEqual(result['body']['zone'], expected_zone)
    self.assertEqual(result['body'].get('metadata'), expected_metadata)
    self.assertEqual(result['body'].get('tags', []), [])
    self.assertEqual(exceptions, [])

  def testAddInstanceGeneratesNoExternalIpRequest(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.AddInstance('addinstance', flag_values)
    service_version = command_base.CURRENT_VERSION
    expected_project = 'test_project'
    expected_instance = 'test_instance'
    expected_description = 'test instance'
    submitted_image = 'expected_image'
    submitted_machine_type = 'goes_to_11'
    submitted_zone = 'copernicus-moon-base'

    expected_authorized_ssh_keys = []
    flag_values.service_version = service_version
    flag_values.zone = submitted_zone
    flag_values.project = expected_project
    flag_values.description = expected_description
    flag_values.image = submitted_image
    flag_values.external_ip_address = 'None'
    flag_values.machine_type = submitted_machine_type
    flag_values.use_compute_key = False
    flag_values.authorized_ssh_keys = expected_authorized_ssh_keys
    flag_values.add_compute_key_to_project = False

    self._instances.list = mock_api.CommandExecutor(self._instance_list)

    command.SetFlags(flag_values)
    command._projects_api = self._projects
    command._instances_api = self._instances
    command._zones_api = self._zones
    command._credential = mock_api.MockCredential()

    expected_metadata = {'kind': 'compute#metadata',
                         'items': []}

    expected_image = command.NormalizeResourceName(expected_project,
                                                   'images',
                                                   submitted_image)

    expected_zone = command.NormalizeResourceName(
        expected_project,
        'zones',
        submitted_zone)

    (results, exceptions) = command.Handle(expected_instance)
    result = results['items'][0]

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['body']['name'], expected_instance)
    self.assertEqual(result['body']['description'], expected_description)
    self.assertEqual(result['body']['image'], expected_image)
    self.assertFalse('accessConfigs' in result['body']['networkInterfaces'][0])
    self.assertEqual(result['body']['zone'], expected_zone)
    self.assertEqual(result['body'].get('metadata'), expected_metadata)
    self.assertEqual(result['body'].get('tags', []), [])
    self.assertEqual(exceptions, [])

  def testAddInstanceRequiresZone(self):
    flag_values = copy.deepcopy(FLAGS)

    command = instance_cmds.AddInstance('addinstance', flag_values)

    service_version = command_base.CURRENT_VERSION
    expected_project = 'test_project'
    expected_instance = 'test_instance'
    expected_description = 'test instance'
    submitted_image = 'expected_image'
    submitted_machine_type = 'goes_to_11'
    submitted_zone = 'us-east-a'
    expected_authorized_ssh_keys = []
    flag_values.service_version = service_version
    flag_values.project = expected_project
    flag_values.description = expected_description
    flag_values.image = submitted_image
    flag_values.machine_type = submitted_machine_type
    flag_values.use_compute_key = False
    flag_values.authorized_ssh_keys = expected_authorized_ssh_keys
    flag_values.add_compute_key_to_project = False

    command.SetFlags(flag_values)
    command._credential = mock_api.MockCredential()

    mock_output = mock_api.MockOutput()
    mock_input = mock_api.MockInput('1\n\r')

    oldin = sys.stdin
    sys.stdin = mock_input
    oldout = sys.stdout
    sys.stdout = mock_output

    def GetZonePath(part_one, part_two, part_three):
      return 'projects/test_project/zones/%s-%s-%s' % (part_one,
                                                       part_two,
                                                       part_three)

    self._instances.list = mock_api.CommandExecutor(self._instance_list)
    self._zones.list = mock_api.CommandExecutor(
        {'items': [
            {'name': GetZonePath('us', 'east', 'a')},
            {'name': GetZonePath('us', 'east', 'b')},
            {'name': GetZonePath('us', 'east', 'c')},
            {'name': GetZonePath('us', 'west', 'a')}]})

    command._projects_api = self._projects
    command._instances_api = self._instances
    command._zones_api = self._zones

    expected_zone = command.NormalizeResourceName(
        expected_project,
        'zones',
        submitted_zone)

    (results, exceptions) = command.Handle(expected_instance)
    result = results['items'][0]

    self.assertEqual(result['body']['zone'], expected_zone)
    self.assertEqual(exceptions, [])
    sys.stdin = oldin
    sys.stdout = oldout

  def _doTestAddInstanceWithServiceAccounts(self,
                                            expected_service_account,
                                            expected_scopes,
                                            should_succeed):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.AddInstance('addinstance', flag_values)

    expected_project = 'test_project'
    expected_instance = 'test_instance'
    expected_description = 'test instance'
    submitted_image = 'expected_image'
    service_version = 'v1beta12'
    submitted_machine_type = 'goes_to_11'
    submitted_zone = 'copernicus-moon-base'
    expected_authorized_ssh_keys = []
    flag_values.service_version = service_version
    flag_values.zone = submitted_zone
    flag_values.project = expected_project
    flag_values.description = expected_description
    flag_values.image = submitted_image
    flag_values.external_ip_address = 'None'
    flag_values.machine_type = submitted_machine_type
    flag_values.use_compute_key = False
    flag_values.authorized_ssh_keys = expected_authorized_ssh_keys
    if expected_service_account:
      # addinstance command checks whether --service_account is explicitly
      # given, so in this case, set the present flag along with the value.
      flag_values['service_account'].present = True
      flag_values.service_account = expected_service_account
    else:
      # The default 'default' will be expected after command.Handle.
      expected_service_account = 'default'
    if expected_scopes:
      flag_values.service_account_scopes = expected_scopes
    else:
      # The default [] will be expected after command.Handle.
      expected_scopes = []
    flag_values.add_compute_key_to_project = False

    self._instances.list = mock_api.CommandExecutor(self._instance_list)

    command.SetFlags(flag_values)
    command._projects_api = self._projects
    command._instances_api = self._instances
    command._zones_api = self._zones
    command._credential = mock_api.MockCredential()

    expected_metadata = {'kind': 'compute#metadata',
                         'items': []}

    expected_image = command.NormalizeResourceName(expected_project,
                                                   'images',
                                                   submitted_image)

    expected_zone = command.NormalizeResourceName(
        expected_project,
        'zones',
        submitted_zone)

    if not should_succeed:
      self.assertRaises(app.UsageError,
                        command.Handle,
                        expected_instance)
    else:
      (results, exceptions) = command.Handle(expected_instance)
      result = results['items'][0]

      self.assertEqual(result['project'], expected_project)
      self.assertEqual(result['body']['name'], expected_instance)
      self.assertEqual(result['body']['description'], expected_description)
      self.assertEqual(result['body']['image'], expected_image)
      self.assertFalse('accessConfigs' in
                       result['body']['networkInterfaces'][0])
      self.assertEqual(result['body']['zone'], expected_zone)
      self.assertEqual(result['body'].get('metadata'), expected_metadata)
      self.assertEqual(result['body'].get('tags', []), [])
      self.assertEqual(result['body']['serviceAccounts'][0]['email'],
                       expected_service_account)
      self.assertEqual(result['body']['serviceAccounts'][0]['scopes'],
                       sorted(expected_scopes))
      self.assertEqual(exceptions, [])

  def testAddInstanceWithServiceAccounts(self):
    email = 'random.default@developer.googleusercontent.com'
    scope1 = 'https://www.googleapis.com/auth/fake.product1'
    scope2 = 'https://www.googleapis.com/auth/fake.product2'
    self._doTestAddInstanceWithServiceAccounts(None, [scope1], True)
    self._doTestAddInstanceWithServiceAccounts(email, [scope1], True)
    self._doTestAddInstanceWithServiceAccounts(email, [scope1, scope2], True)
    self._doTestAddInstanceWithServiceAccounts(email, None, False)

  def testAddInstanceWithUnknownKeyFile(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.AddInstance('addinstance', flag_values)

    submitted_machine_type = 'goes_to_11'
    submitted_zone = 'copernicus-moon-base'
    expected_instance = 'test_instance'
    flag_values.project = 'test_project'
    flag_values.zone = submitted_zone
    flag_values.description = 'test instance'
    flag_values.image = 'expected_image'
    flag_values.machine_type = submitted_machine_type
    flag_values.use_compute_key = False
    flag_values.authorized_ssh_keys = ['user:unknown-file']
    flag_values.add_compute_key_to_project = False

    self._instances.list = mock_api.CommandExecutor(self._instance_list)

    command.SetFlags(flag_values)
    command._projects_api = self._projects
    command._instances_api = self._instances
    command._zones_api = self._zones
    command._credential = mock_api.MockCredential()

    self.assertRaises(IOError,
                      command.Handle,
                      expected_instance)

  def testAddAuthorizedUserKeyToProject(self):
    flag_values = copy.deepcopy(FLAGS)
    flag_values.service_version = 'v1beta12'
    command = instance_cmds.AddInstance('addinstance', flag_values)

    class SetCommonInstanceMetadata(object):
      def __init__(self, record):
        self.record = record

      def __call__(self, project, body):
        self.record['project'] = project
        self.record['body'] = body
        return self

      def execute(self):
        pass

    ssh_keys = ''
    self._projects.get = mock_api.CommandExecutor(
        {'commonInstanceMetadata': {
            'kind': 'compute#metadata',
            'items': [{'key': 'sshKeys', 'value': ssh_keys}]}})
    call_record = {}
    self._projects.setCommonInstanceMetadata = SetCommonInstanceMetadata(
        call_record)
    expected_project = 'test_project'

    flag_values.service_version = 'v1beta12'
    flag_values.project = expected_project
    command.SetFlags(flag_values)
    command._projects_api = self._projects
    command._credential = mock_api.MockCredential()

    result = command._AddAuthorizedUserKeyToProject(
        {'user': 'foo', 'key': 'bar'})
    self.assertTrue(result)
    self.assertEquals(expected_project, call_record['project'])
    self.assertEquals(
        {'kind': 'compute#metadata',
         'items': [{'key': 'sshKeys', 'value': 'foo:bar'}]},
        call_record['body'])

  def testAddAuthorizedUserKeyAlreadyInProject(self):
    flag_values = copy.deepcopy(FLAGS)
    flag_values.service_version = 'v1beta12'
    command = instance_cmds.AddInstance('addinstance', flag_values)

    class SetCommonInstanceMetadata(object):
      def __init__(self, record):
        self.record = record

      def __call__(self, project, body):
        self.record['project'] = project
        self.record['body'] = body
        return self

      def execute(self):
        pass

    ssh_keys = 'baz:bat\nfoo:bar\ni:j'
    self._projects.get = mock_api.CommandExecutor(
        {'commonInstanceMetadata': {
            'kind': 'compute#metadata',
            'items': [{'key': 'sshKeys', 'value': ssh_keys}]}})
    call_record = {}
    self._projects.setCommonInstanceMetadata = SetCommonInstanceMetadata(
        call_record)
    expected_project = 'test_project'

    flag_values.service_version = 'v1beta12'
    flag_values.project = expected_project
    command.SetFlags(flag_values)
    command._projects_api = self._projects
    command._credential = mock_api.MockCredential()

    result = command._AddAuthorizedUserKeyToProject(
        {'user': 'foo', 'key': 'bar'})
    self.assertFalse(result)

  def _testAddSshKeysToMetadataHelper(self,
                                      test_ssh_key_through_file,
                                      test_ssh_key_through_flags):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.AddInstance('addinstance', flag_values)
    flag_values.use_compute_key = False
    ssh_rsa_key = ('ssh-rsa ' +
                   base64.b64encode('\00\00\00\07ssh-rsa the ssh key') +
                   ' comment')

    with tempfile.NamedTemporaryFile() as metadata_file:
      with tempfile.NamedTemporaryFile() as ssh_key_file:
        metadata_file.write('metadata file content')
        metadata_file.flush()
        flag_values.metadata_from_file = ['bar_file:%s' % metadata_file.name]

        flag_values.metadata = ['bar:baz']

        if test_ssh_key_through_file:
          ssh_key_file.write(ssh_rsa_key)
          ssh_key_file.flush()
          flag_values.authorized_ssh_keys = ['user:%s' % ssh_key_file.name]

        if test_ssh_key_through_flags:
          flag_values.metadata.append('sshKeys:user2:flags ssh key')

        command.SetFlags(flag_values)
        metadata_flags_processor = command._metadata_flags_processor
        extended_metadata = command._AddSshKeysToMetadata(
            metadata_flags_processor.GatherMetadata())

    self.assertTrue(len(extended_metadata) >= 2)
    self.assertEqual(extended_metadata[0]['key'], 'bar')
    self.assertEqual(extended_metadata[0]['value'], 'baz')
    self.assertEqual(extended_metadata[1]['key'], 'bar_file')
    self.assertEqual(extended_metadata[1]['value'], 'metadata file content')

    ssh_keys = []
    if test_ssh_key_through_flags:
      ssh_keys.append('user2:flags ssh key')
    if test_ssh_key_through_file:
      ssh_keys.append('user:' + ssh_rsa_key)

    if test_ssh_key_through_flags or test_ssh_key_through_file:
      self.assertEqual(len(extended_metadata), 3)
      self.assertEqual(extended_metadata[2]['key'], 'sshKeys')
      self.assertEqual(extended_metadata[2]['value'],
                       '\n'.join(ssh_keys))

  def testGatherMetadata(self):
    self._testAddSshKeysToMetadataHelper(False, False)
    self._testAddSshKeysToMetadataHelper(False, True)
    self._testAddSshKeysToMetadataHelper(True, False)
    self._testAddSshKeysToMetadataHelper(True, True)

  def testBuildInstanceRequestWithMetadataAndDisk(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.AddInstance('addinstance', flag_values)

    expected_project = 'test_project'
    expected_instance = 'test_instance'
    expected_description = 'test instance'
    submitted_image = 'expected_image'
    submitted_zone = 'copernicus-moon-base'
    flag_values.service_version = 'v1beta12'
    flag_values.project = expected_project
    flag_values.zone = submitted_zone
    flag_values.description = expected_description
    flag_values.image = submitted_image
    flag_values.use_compute_key = False
    flag_values.authorized_ssh_keys = []
    flag_values.add_compute_key_to_project = False
    metadata = [{'key': 'foo', 'value': 'bar'}]
    disks = [{'source': ('http://www.googleapis.com/compute/v1beta12/projects/'
                         'google.com:test/disks/disk789'),
              'deviceName': 'disk789', 'mode': 'READ_WRITE',
              'type': 'PERSISTENT', 'boot': False}]

    expected_metadata = {'kind': 'compute#metadata',
                         'items': metadata}

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())

    result = command._BuildRequestWithMetadata(
        expected_instance, metadata, disks).execute()

    expected_image = command.NormalizeResourceName(expected_project,
                                                   'images',
                                                   submitted_image)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['body']['name'], expected_instance)
    self.assertEqual(result['body']['description'], expected_description)
    self.assertEqual(result['body']['image'], expected_image)
    self.assertEqual(result['body']['metadata'], expected_metadata)
    self.assertEqual(result['body']['disks'], disks)

  def testBuildInstanceRequestWithTag(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.AddInstance('addinstance', flag_values)

    service_version = 'v1beta12'
    expected_project = 'test_project'
    expected_instance = 'test_instance'
    expected_description = 'test instance'
    submitted_image = 'expected_image'
    submitted_machine_type = 'goes_to_11'
    submitted_zone = 'copernicus-moon-base'
    expected_tags = ['tag0', 'tag1', 'tag2']

    flag_values.service_version = service_version
    flag_values.project = expected_project
    flag_values.zone = submitted_zone
    flag_values.description = expected_description
    flag_values.image = submitted_image
    flag_values.machine_type = submitted_machine_type
    flag_values.use_compute_key = False
    flag_values.authorized_ssh_keys = []
    flag_values.tags = expected_tags * 2  # Create duplicates.
    flag_values.add_compute_key_to_project = False

    self._instances.list = mock_api.CommandExecutor(self._instance_list)

    command.SetFlags(flag_values)
    command._projects_api = self._projects
    command._instances_api = self._instances
    command._zones_api = self._zones
    command._credential = mock_api.MockCredential()

    expected_metadata = {'kind': 'compute#metadata',
                         'items': []}

    expected_image = command.NormalizeResourceName(expected_project,
                                                   'images',
                                                   submitted_image)

    expected_zone = command.NormalizeResourceName(
        expected_project,
        'zones',
        submitted_zone)

    (results, exceptions) = command.Handle(expected_instance)
    result = results['items'][0]

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['body']['name'], expected_instance)
    self.assertEqual(result['body']['description'], expected_description)
    self.assertEqual(result['body']['image'], expected_image)
    self.assertFalse(
        'natIP' in result['body']['networkInterfaces'][0]['accessConfigs'][0],
        result)
    self.assertEqual(result['body']['zone'], expected_zone)
    self.assertEqual(result['body'].get('metadata'), expected_metadata)
    self.assertEqual(result['body'].get('tags'), expected_tags)
    self.assertEqual(exceptions, [])

  def testGetInstanceGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.GetInstance('getinstance', flag_values)

    expected_project = 'test_project'
    expected_instance = 'test_instance'
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    result = command.Handle(expected_instance)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['instance'], expected_instance)

  def testDeleteInstanceGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.DeleteInstance('deleteinstance', flag_values)

    expected_project = 'test_project'
    expected_instance = 'test_instance'
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    (results, exceptions) = command.Handle(expected_instance)
    result = results['items'][0]

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['instance'], expected_instance)
    self.assertEqual(exceptions, [])

  def testDeleteMultipleInstances(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.DeleteInstance('deleteinstance', flag_values)

    expected_project = 'test_project'
    expected_instances = ['test-instance-%02d' % i for i in range(100)]
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    (results, exceptions) = command.Handle(*expected_instances)
    self.assertEqual(exceptions, [])
    results = results['items']
    self.assertEqual(len(results), len(expected_instances))

    for (expected_instance, result) in zip(expected_instances, results):
      self.assertEqual(result['project'], expected_project)
      self.assertEqual(result['instance'], expected_instance)

  def testListInstancesGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.ListInstances('listinstances', flag_values)

    expected_project = 'test_project'
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    result = command.Handle()

    self.assertEqual(result['project'], expected_project)

  def testAddAccessConfigGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.AddAccessConfig('addaccessconfig', flag_values)

    expected_project_name = 'test_project_name'
    expected_instance_name = 'test_instance_name'
    expected_network_interface_name = 'test_network_interface_name'
    expected_access_config_name = 'test_access_config_name'
    expected_access_config_type = 'test_access_config_type'
    expected_access_config_nat_ip = 'test_access_config_nat_ip'

    flag_values.project = expected_project_name
    flag_values.network_interface_name = expected_network_interface_name
    flag_values.access_config_name = expected_access_config_name
    flag_values.access_config_type = expected_access_config_type
    flag_values.access_config_nat_ip = expected_access_config_nat_ip
    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    result = command.Handle(expected_instance_name)

    self.assertEqual(result['project'], expected_project_name)
    self.assertEqual(result['instance'], expected_instance_name)
    self.assertEqual(result['network_interface'],
                     expected_network_interface_name)
    self.assertEqual(result['body']['name'], expected_access_config_name)
    self.assertEqual(result['body']['type'], expected_access_config_type)
    self.assertEqual(result['body']['natIP'], expected_access_config_nat_ip)

  def testDeleteAccessConfigGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.DeleteAccessConfig('deleteaccessconfig',
                                               flag_values)

    expected_project_name = 'test_project_name'
    expected_instance_name = 'test_instance_name'
    expected_network_interface_name = 'test_network_interface_name'
    expected_access_config_name = 'test_access_config_name'

    flag_values.project = expected_project_name
    flag_values.network_interface_name = expected_network_interface_name
    flag_values.access_config_name = expected_access_config_name
    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    result = command.Handle(expected_instance_name)

    self.assertEqual(result['project'], expected_project_name)
    self.assertEqual(result['instance'], expected_instance_name)
    self.assertEqual(result['network_interface'],
                     expected_network_interface_name)
    self.assertEqual(result['access_config'],
                     expected_access_config_name)

  def testGetSshAddressChecksForNetworkInterfaces(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.SshInstanceBase('test', flag_values)
    command.SetFlags(flag_values)
    mock_instance = {'someFieldOtherThanNetworkInterfaces': [],
                     'status': 'RUNNING'}

    self.assertRaises(command_base.CommandError,
                      command._GetSshAddress,
                      mock_instance)

  def testGetSshAddressChecksForNonEmptyNetworkInterfaces(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.SshInstanceBase('test', flag_values)
    command.SetFlags(flag_values)
    mock_instance = {'networkInterfaces': [], 'status': 'RUNNING'}

    self.assertRaises(command_base.CommandError,
                      command._GetSshAddress,
                      mock_instance)

  def testGetSshAddressChecksForAccessConfigs(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.SshInstanceBase('test', flag_values)
    command.SetFlags(flag_values)
    mock_instance = {'networkInterfaces': [{}]}

    self.assertRaises(command_base.CommandError,
                      command._GetSshAddress,
                      mock_instance)

  def testGetSshAddressChecksForNonEmptyAccessConfigs(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.SshInstanceBase('test', flag_values)
    command.SetFlags(flag_values)
    mock_instance = {'networkInterfaces': [{'accessConfigs': []}],
                     'status': 'RUNNING'}

    self.assertRaises(command_base.CommandError,
                      command._GetSshAddress,
                      mock_instance)

  def testGetSshAddressChecksForNatIp(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.SshInstanceBase('test', flag_values)
    command.SetFlags(flag_values)
    mock_instance = {'networkInterfaces': [{'accessConfigs': [{}]}],
                     'status': 'RUNNING'}

    self.assertRaises(command_base.CommandError,
                      command._GetSshAddress,
                      mock_instance)

  def testEnsureSshableChecksForSshKeysInTheInstance(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.SshInstanceBase('test', flag_values)
    command.SetFlags(flag_values)
    mock_instance = {'networkInterfaces': [{'accessConfigs': [{}]}],
                     'status': 'RUNNING',
                     'metadata': {u'kind': u'compute#metadata',
                                  u'items': [{u'key': u'sshKeys',
                                              u'value': ''}]}}

    def MockAddComputeKeyToProject():
      self.fail('Unexpected call to _AddComputeKeyToProject')

    command._AddComputeKeyToProject = MockAddComputeKeyToProject
    command._EnsureSshable(mock_instance)

  def testEnsureSshableChecksForNonRunningInstance(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.SshInstanceBase('test', flag_values)
    command.SetFlags(flag_values)
    mock_instance = {'networkInterfaces': [{'accessConfigs': [{}]}],
                     'status': 'STAGING'}

    self.assertRaises(command_base.CommandError,
                      command._EnsureSshable,
                      mock_instance)

  def testSshGeneratesCorrectArguments(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.SshToInstance('ssh', flag_values)

    argv = ['arg1', '%arg2', 'arg3']
    expected_arg_list = ['-A', '-p', '%(port)d', '%(user)s@%(host)s',
                         '--', 'arg1', '%%arg2', 'arg3']

    arg_list = command._GenerateSshArgs(*argv)

    self.assertEqual(expected_arg_list, arg_list)

  def testSshPassesThroughSshArg(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.SshToInstance('ssh', flag_values)
    ssh_arg = '--passedSshArgKey=passedSshArgValue'
    flag_values.ssh_arg = [ssh_arg]
    command.SetFlags(flag_values)
    ssh_args = command._GenerateSshArgs(*[])
    mock_instance_resource = {
        'networkInterfaces': [{'accessConfigs': [{'type': 'ONE_TO_ONE_NAT',
                                                  'natIP': '0.0.0.0'}]}],
        'status': 'RUNNING'}
    command_line = command._BuildSshCmd(mock_instance_resource, 'ssh', ssh_args)
    self.assertTrue(ssh_arg in command_line)

  def testSshPassesThroughTwoSshArgs(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.SshToInstance('ssh', flag_values)
    ssh_arg1 = '--k1=v1'
    ssh_arg2 = '--k2=v2'
    flag_values.ssh_arg = [ssh_arg1, ssh_arg2]
    command.SetFlags(flag_values)
    ssh_args = command._GenerateSshArgs(*[])
    mock_instance_resource = {
        'networkInterfaces': [{'accessConfigs': [{'type': 'ONE_TO_ONE_NAT',
                                                  'natIP': '0.0.0.0'}]}],
        'status': 'RUNNING'}
    command_line = command._BuildSshCmd(mock_instance_resource, 'ssh', ssh_args)

    self.assertTrue(ssh_arg1 in command_line)
    self.assertTrue(ssh_arg2 in command_line)

  def testSshGeneratesCorrectCommand(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.SshToInstance('ssh', flag_values)

    expected_project = 'test_project'
    expected_ip = '1.1.1.1'
    expected_port = 22
    expected_user = 'test_user'
    expected_ssh_file = 'test_file'
    flag_values.project = expected_project
    flag_values.ssh_port = expected_port
    flag_values.ssh_user = expected_user
    flag_values.private_key_file = expected_ssh_file

    ssh_args = ['-A', '-p', '%(port)d', '%(user)s@%(host)s', '--']

    expected_command = [
        'ssh', '-o', 'UserKnownHostsFile=/dev/null',
        '-o', 'CheckHostIP=no',
        '-o', 'StrictHostKeyChecking=no',
        '-i', expected_ssh_file,
        '-A', '-p', str(expected_port),
        '%s@%s' % (expected_user, expected_ip),
        '--']

    if LOGGER.level <= logging.DEBUG:
      expected_command.insert(-5, '-v')

    command.SetFlags(flag_values)
    mock_instance_resource = {
        'networkInterfaces': [{'accessConfigs': [{'type': 'ONE_TO_ONE_NAT',
                                                  'natIP': expected_ip}]}],
        'status': 'RUNNING'}
    command_line = command._BuildSshCmd(mock_instance_resource, 'ssh', ssh_args)

    self.assertEqual(expected_command, command_line)

  def testScpPushGeneratesCorrectArguments(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.PushToInstance('push', flag_values)

    argv = ['file1', '%file2', 'destination']
    expected_arg_list = ['-r', '-P', '%(port)d', '--',
                         'file1',
                         '%%file2',
                         '%(user)s@%(host)s:destination']

    arg_list = command._GenerateScpArgs(*argv)

    self.assertEqual(expected_arg_list, arg_list)

  def testScpPushGeneratesCorrectCommand(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.PushToInstance('push', flag_values)

    expected_project = 'test_project'
    expected_ip = '1.1.1.1'
    expected_port = 22
    expected_user = 'test_user'
    expected_ssh_file = 'test_file'
    expected_local_file = 'test_source'
    expected_remote_file = 'test_remote'
    flag_values.project = expected_project
    flag_values.ssh_port = expected_port
    flag_values.ssh_user = expected_user
    flag_values.private_key_file = expected_ssh_file

    scp_args = ['-P', '%(port)d', '--']
    unused_argv = ('', expected_local_file, expected_remote_file)

    escaped_args = [a.replace('%', '%%') for a in unused_argv]
    scp_args.extend(escaped_args[1:-1])
    scp_args.append('%(user)s@%(host)s:' + escaped_args[-1])

    expected_command = [
        'scp',
        '-o', 'UserKnownHostsFile=/dev/null',
        '-o', 'CheckHostIP=no',
        '-o', 'StrictHostKeyChecking=no',
        '-i', expected_ssh_file,
        '-P', str(expected_port),
        '--', expected_local_file,
        '%s@%s:%s' % (expected_user, expected_ip, expected_remote_file)]

    if LOGGER.level <= logging.DEBUG:
      expected_command.insert(-5, '-v')

    command.SetFlags(flag_values)
    mock_instance_resource = {
        'networkInterfaces': [{'accessConfigs': [{'type': 'ONE_TO_ONE_NAT',
                                                  'natIP': expected_ip}]}],
        'status': 'RUNNING'}

    command_line = command._BuildSshCmd(mock_instance_resource, 'scp', scp_args)

    self.assertEqual(expected_command, command_line)

  def testScpPullGeneratesCorrectArguments(self):
    class MockGetApi(object):
      def __init__(self, nat_ip='0.0.0.0'):
        self._nat_ip = nat_ip

      def instances(self):
        return self

      def get(self, *unused_args, **unused_kwargs):
        return self

      def execute(self):
        return {'status': 'RUNNING'}

    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.PullFromInstance('pull', flag_values)

    command._instances_api = MockGetApi()

    argv = ['file1', '%file2', 'destination']
    expected_arg_list = ['-r', '-P', '%(port)d', '--',
                         '%(user)s@%(host)s:file1',
                         '%(user)s@%(host)s:%%file2',
                         'destination']

    arg_list = command._GenerateScpArgs(*argv)

    self.assertEqual(expected_arg_list, arg_list)

  def testScpPullGeneratesCorrectCommand(self):
    flag_values = copy.deepcopy(FLAGS)
    command = instance_cmds.PushToInstance('push', flag_values)

    expected_project = 'test_project'
    expected_ip = '1.1.1.1'
    expected_port = 22
    expected_user = 'test_user'
    expected_ssh_file = 'test_file'
    expected_local_file = 'test_source'
    expected_remote_file = 'test_remote'
    flag_values.project = expected_project
    flag_values.ssh_port = expected_port
    flag_values.ssh_user = expected_user
    flag_values.private_key_file = expected_ssh_file

    scp_args = ['-P', '%(port)d', '--']
    unused_argv = ('', expected_remote_file, expected_local_file)

    escaped_args = [a.replace('%', '%%') for a in unused_argv]
    for arg in escaped_args[1:-1]:
      scp_args.append('%(user)s@%(host)s:' + arg)
    scp_args.append(escaped_args[-1])

    expected_command = [
        'scp',
        '-o', 'UserKnownHostsFile=/dev/null',
        '-o', 'CheckHostIP=no',
        '-o', 'StrictHostKeyChecking=no',
        '-i', expected_ssh_file,
        '-P', str(expected_port),
        '--', '%s@%s:%s' % (expected_user, expected_ip, expected_remote_file),
        expected_local_file
        ]
    if LOGGER.level <= logging.DEBUG:
      expected_command.insert(-5, '-v')

    command.SetFlags(flag_values)
    mock_instance_resource = {
        'networkInterfaces': [{'accessConfigs': [{'type': 'ONE_TO_ONE_NAT',
                                                  'natIP': expected_ip}]}],
        'status': 'RUNNING'}

    command_line = command._BuildSshCmd(mock_instance_resource, 'scp', scp_args)
    self.assertEqual(expected_command, command_line)


if __name__ == '__main__':
  unittest.main()
