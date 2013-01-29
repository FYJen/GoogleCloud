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

"""Unit tests for the asynchronous operations commands."""



import path_initializer
path_initializer.initialize_sys_path()

import copy

import gflags as flags
import unittest

from gcutil import mock_api
from gcutil import operation_cmds

FLAGS = flags.FLAGS


class OperationCmdsTest(unittest.TestCase):

  def testGetOperationGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = operation_cmds.GetOperation('getoperation', flag_values)

    expected_project = 'test_project'
    expected_operation = 'test_operation'
    service_version = 'v1beta12'
    flag_values.project = expected_project
    flag_values.service_version = service_version

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())

    result = command.Handle(expected_operation)

    self.assertEqual(result['project'], expected_project)
    self.assertEqual(result['operation'], expected_operation)

  def testDeleteOperationGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = operation_cmds.DeleteOperation('deleteoperation', flag_values)

    expected_project = 'test_project'
    expected_operation = 'test_operation'
    service_version = 'v1beta12'
    flag_values.project = expected_project
    flag_values.service_version = service_version

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(expected_operation)
    self.assertEqual(exceptions, [])
    self.assertEqual(results, '')

  def testDeleteMultipleOperations(self):
    flag_values = copy.deepcopy(FLAGS)
    command = operation_cmds.DeleteOperation('deleteoperation', flag_values)

    expected_project = 'test_project'
    expected_operations = ['test-operation-%02d' % x for x in xrange(100)]
    flag_values.project = expected_project

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())
    command._credential = mock_api.MockCredential()

    results, exceptions = command.Handle(*expected_operations)
    self.assertEqual(exceptions, [])
    self.assertEqual(results, '')

  def testListOperationsGeneratesCorrectRequest(self):
    flag_values = copy.deepcopy(FLAGS)

    command = operation_cmds.ListOperations('listoperations', flag_values)

    expected_project = 'test_project'
    service_version = 'v1beta12'
    flag_values.project = expected_project
    flag_values.service_version = service_version

    command.SetFlags(flag_values)
    command.SetApi(mock_api.MockApi())

    result = command.Handle()

    self.assertEqual(result['project'], expected_project)

if __name__ == '__main__':
  unittest.main()
