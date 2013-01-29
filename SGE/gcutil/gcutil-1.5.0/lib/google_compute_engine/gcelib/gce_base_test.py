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

"""Tests for gce_base."""

from email.mime.nonmultipart import MIMENonMultipart
import itertools
import json
import logging
import random
import re
import unittest

import httplib2

from gcelib import gce
from gcelib import gce_base


class OperationMock(object):

  @staticmethod
  def load_from_dict(unused_val, unused_gce):
    return OperationMock()


class InstanceMock(object):

  @staticmethod
  def load_from_dict(unused_val, unused_gce):
    return InstanceMock()


def get_mock_parsers():
  """Returns a dict making kinds to parsers."""
  return {
      'compute#operation': OperationMock.load_from_dict,
      'compute#instance': InstanceMock.load_from_dict}


class GoogleComputeEngineBaseTests(unittest.TestCase):
  """Tests for GoogleComputeEngineBase."""

  def setUp(self):
    self.gce = gce_base.GoogleComputeEngineBase(
        None,
        logging_level=logging.DEBUG,
        base_url='https://www.googleapis.com/compute/v1/projects/')

  def tearDown(self):
    pass

  def test_normalize(self):
    """Tests resource normalization."""
    self.assertEqual(
        self.gce._normalize('my-project', 'instances', 'my-instance'),
        'https://www.googleapis.com/compute/v1/projects/my-project/instances/'
        'my-instance')

    self.assertEqual(
        self.gce._normalize('my-project', 'instances', 'instances/my-instance'),
        'https://www.googleapis.com/compute/v1/projects/my-project/instances/'
        'my-instance')

    self.assertEqual(
        self.gce._normalize('my-project', 'instances',
                            'projects/my-project/instances/my-instance'),
        'https://www.googleapis.com/compute/v1/projects/my-project/instances/'
        'my-instance')

    self.assertEqual(
        self.gce._normalize('my-project', 'instances', 'instances'),
        'https://www.googleapis.com/compute/v1/projects/my-project/instances/'
        'instances')

    self.assertEqual(
        self.gce._normalize('projectsprojects', 'instances',
                            'projects/projectsprojects/instances/my-instance'),
        'https://www.googleapis.com/compute/v1/projects/projectsprojects/'
        'instances/my-instance')

    self.assertEqual(
        self.gce._normalize('my-project', 'images', 'ubuntu-12-04-v20120503'),
        'https://www.googleapis.com/compute/v1/projects/my-project/images/'
        'ubuntu-12-04-v20120503')

    self.assertEqual(
        self.gce._normalize('my-project', 'images',
                            'projects/google/images/ubuntu-12-04-v20120503'),
        'https://www.googleapis.com/compute/v1/projects/google/images/'
        'ubuntu-12-04-v20120503')

  def test_defaults(self):
    """Tests the default properties."""
    self.assertEqual(self.gce.default_image, None)
    self.assertEqual(self.gce.default_machine_type, None)
    self.assertEqual(
        self.gce.default_network_interface,
        [{'accessConfigs': [{'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}],
          'network': 'default'}])
    self.assertEqual(self.gce.default_network, 'default')
    self.assertEqual(self.gce.default_project, None)
    self.assertEqual(self.gce.default_zone, None)

    self.gce.default_image = (
        'projects/google/images/ubuntu-12-04-v20120503')
    self.gce.default_machine_type = 'n1-standard-1-ssd'
    self.gce.default_network = 'my-network'
    self.gce.default_network_interface = (
        [{'accessConfigs': [{'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}],
          'network': 'my-network-interface'}])
    self.gce.default_project = 'my-project'
    self.gce.default_zone = 'us-east-a'

    self.assertEqual(self.gce.default_image,
                     'projects/google/images/ubuntu-12-04-v20120503')
    self.assertEqual(self.gce.default_machine_type, 'n1-standard-1-ssd')
    self.assertEqual(self.gce.default_network, 'my-network')
    self.assertEqual(
        self.gce.default_network_interface,
        [{'accessConfigs': [{'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}],
          'network': 'my-network-interface'}])
    self.assertEqual(self.gce.default_project, 'my-project')
    self.assertEqual(self.gce.default_zone, 'us-east-a')

    del self.gce.default_image
    del self.gce.default_machine_type
    del self.gce.default_network
    del self.gce.default_network_interface
    del self.gce.default_project
    del self.gce.default_zone

    self.assertEqual(self.gce.default_image, None)
    self.assertEqual(self.gce.default_machine_type, None)
    self.assertEqual(self.gce.default_network, 'default')
    self.assertEqual(
        self.gce.default_network_interface,
        [{'accessConfigs': [{'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}],
          'network': 'default'}])
    self.assertEqual(self.gce.default_project, None)
    self.assertEqual(self.gce.default_zone, None)

    gce = gce_base.GoogleComputeEngineBase(
        None,
        default_image='projects/google/images/ubuntu-12-04-v20120503',
        default_machine_type='n1-standard-1-ssd',
        default_network='my-network',
        default_network_interface=(
            [{'accessConfigs': [{'type': 'ONE_TO_ONE_NAT',
                                 'name': 'External NAT'}],
              'network': 'my-network-interface'}]),
        default_project='my-project',
        default_zone='us-east-a')

    self.assertEqual(gce.default_image,
                     'projects/google/images/ubuntu-12-04-v20120503')
    self.assertEqual(gce.default_machine_type, 'n1-standard-1-ssd')
    self.assertEqual(gce.default_network, 'my-network')
    self.assertEqual(
        gce.default_network_interface,
        [{'accessConfigs': [{'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}],
          'network': 'my-network-interface'}])
    self.assertEqual(gce.default_project, 'my-project')
    self.assertEqual(gce.default_zone, 'us-east-a')

    gce = gce_base.GoogleComputeEngineBase(
        None,
        default_network='my-network')
    self.assertEqual(
        gce.default_network_interface,
        [{'accessConfigs': [{'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}],
          'network': 'my-network'}])

  def test_trace_token(self):
    self.assertEqual(self.gce.trace_token, None)
    self.gce.trace_token = 'TRACE_TOKEN'
    self.assertEqual(self.gce.trace_token, 'TRACE_TOKEN')
    del self.gce.trace_token
    self.assertEqual(self.gce.trace_token, None)

    gce = gce_base.GoogleComputeEngineBase(None, trace_token='TRACE_TOKEN')
    self.assertEqual(gce.trace_token, 'TRACE_TOKEN')
    del self.gce.trace_token
    self.assertEqual(self.gce.trace_token, None)

  def test_execute_with_http(self):
    """Ensures that _execute() will not communicate over HTTP."""
    self.assertRaises(ValueError,
                      gce_base.GoogleComputeEngineBase,
                      credentials=None,
                      base_url='http://www.googleapis.com/compute/v1/projects/')

  def test_base_url_checks(self):
    # All these should work
    self.assertRaises(
        ValueError,
        gce_base.GoogleComputeEngineBase,
        credentials=None,
        base_url='https://www.googleapis.com/nocompute/v1/projects/')

  def test_execute(self):
    """Tests _execute()'s ability to build up a correct request URL."""

    def mock_send_request_json(path, method, request_body):
      self.assertEqual(
          path,
          'https://www.googleapis.com/compute/v1/projects/my-project/'
          'instances?filter=name%2Beq%2B%27.%2A%2Fmy_instance_%5B0-9%5D%2B%27'
          '&maxResults=100'
          '&pageToken='
          'CghJTlNUQU5DRRIhNzQyMzg3MDc3NTUuY3JlYXRlZC1qdW4tNi1udW0t')
      self.assertEqual(method, 'GET')
      self.assertEqual(request_body, None)

    query_params = {
        'pageToken': 'CghJTlNUQU5DRRIhNzQyMzg3MDc3NTUuY3JlYXRlZC1qdW4tNi1udW0t',
        'filter': 'name+eq+\'.*/my_instance_[0-9]+\'',
        'maxResults': 100}

    self.gce._send_request_json = mock_send_request_json
    self.gce._execute(gce_base.GoogleComputeEngineBase.API_REQUEST(
        'GET', 'my-project/instances', query_params, None), False)

  def test_convert(self):
    """Ensures that _convert() correctly parses dict and tuples of dicts."""

    def get_empty_parsers():
      """Returns a dict that contains no kind-to-parser mappings."""
      return {}

    self.gce._get_parsers = get_mock_parsers

    self.assertEqual(self.gce._parse(None), None)

    value_error = ValueError()
    self.assertEqual(self.gce._parse(value_error), value_error)

    operation = {
        'status': 'DONE',
        'kind': 'compute#operation',
        'name': '.../operation-1339021242481-4c1d52d7d64f0-63c9dc72',
        'startTime': '2012-06-06T22:20:42.601',
        'insertTime': '2012-06-06T22:20:42.481',
        'targetId': '12884714477555140369',
        'targetLink': 'https://googleapis.com/compute/.../instances/x-1000',
        'operationType': 'insert',
        'progress': 100,
        'endTime': '2012-06-06T22:20:49.268',
        'id': '12907884892091471776',
        'selfLink': 'https://googleapis.com/compute/...d64f0-63c9dc72',
        'user': 'bugsbunny@google.com'}

    instance = {
        'status': 'STAGING',
        'kind': 'compute#instance',
        'machineType': 'https://googleapis.com/compute/.../n1-standard-1',
        'name': 'projects/my-project/instances/x-1000',
        'zone': 'https://googleapis.com/compute/.../zones/us-east-a',
        'tags': [],
        'image': 'https://googleapis.com/compute/.../images/ubuntu',
        'disks': [
            {
                'index': 0,
                'kind': 'compute#instanceDisk',
                'type': 'EPHEMERAL',
                'mode': 'READ_WRITE'
                }
            ],
        'networkInterfaces': [
            {
                'networkIP': '10.211.197.175',
                'kind': 'compute#instanceNetworkInterface',
                'accessConfigs': [
                    {
                        'type': 'ONE_TO_ONE_NAT',
                        'name': 'External NAT',
                        'natIP': '173.255.120.98'
                        }
                    ],
                'name': 'nic0',
                'network': 'https://googleapis.com/compute/.../networks/default'
                }
            ],
        'id': '12884714477555140369',
        'selfLink': 'https://googleapis.com/compute/.../instances/x-1000',
        'description': ''}

    res = self.gce._parse(operation)
    self.assertTrue(isinstance(res, OperationMock))
    res = self.gce._parse(instance)
    self.assertTrue(isinstance(res, InstanceMock))

    del operation['kind']
    self.assertRaises(gce.GceError, self.gce._parse, operation)

    self.gce._get_parsers = get_empty_parsers
    self.assertRaises(gce.GceError, self.gce._parse, instance)

  def test_project_from_self_link(self):
    parse = gce_base.GoogleComputeEngineBase._parse_project

    self.assertEqual(
        parse('http://googleapis.com/compute/v1/projects/my-project'),
        'my-project')
    self.assertEqual(
        parse('https://googleapis.com/compute/v1beta11/projects/my-project/'),
        'my-project')
    self.assertEqual(
        parse('https://googleapis.com/compute/v1beta11/projects'
              '/my-project/instances/foo'),
        'my-project')
    self.assertEqual(
        parse('//googleapis.com/compute/v1beta11/projects/my-project/xxxx'),
        None)
    self.assertEqual(
        parse('http://googleapis.com/invalid/version/projects/my-project'),
        None)
    self.assertEqual(
        parse('http://googleapis.com/compute/version/noprojects/my-project'),
        None)
    self.assertEqual(
        parse('https://googleapis.com/compute/version/projects/'),
        None)

  def test_check_url(self):
    """Ensures that _check_url() raises an exception on bad API URLs."""
    check = gce_base.GoogleComputeEngineBase._check_url
    # Success cases.
    check('https://www.googleapis.com/compute/v1/projects/')
    check('https://www.googleapis.com/compute/v1beta12/projects/')

    # Failure cases.
    self.assertRaises(ValueError, check, '')
    self.assertRaises(ValueError, check,
                      'http://www.googleapis.com/compute/v1/projects/')
    self.assertRaises(ValueError, check,
                      'https://googleapis.com/compute/v1/projects/')
    self.assertRaises(ValueError, check,
                      'https://www.gmail.com/compute/v1/projects/')
    self.assertRaises(ValueError, check,
                      'http://www.googleapis.com/compute//projects/')
    self.assertRaises(ValueError, check,
                      'http://www.googleapis.com/compute/BAD_VERSION/projects/')
    self.assertRaises(ValueError, check,
                      'http://www.googleapis.com/compute/v1/')
    self.assertRaises(ValueError, check,
                      'http://www.googleapis.com/compute/v1/projects')
    self.assertRaises(ValueError, check,
                      'www.googleapis.com/compute/v1/projects')
    self.assertRaises(ValueError, check,
                      'https://www.googleapis.com/v1/projects')

  def test_create_url_query(self):
    """Tests the url query component creation."""
    self.assertEqual('', self.gce._create_url_query(None))
    self.assertEqual('', self.gce._create_url_query({}))
    self.assertEqual('key=value', self.gce._create_url_query({'key': 'value'}))
    self.assertEqual('a=hello&b=hi',
                     self.gce._create_url_query({'a': 'hello', 'b': 'hi'}))

    self.gce.trace_token = 'TRACE_TOKEN'
    self.assertEqual('trace=token%3ATRACE_TOKEN',
                     self.gce._create_url_query(None))
    self.assertEqual('key=value&trace=token%3ATRACE_TOKEN',
                     self.gce._create_url_query({'key': 'value'}))

  def test_parse_list(self):
    resources = [
        {'kind': 'compute#operation'},
        {'kind': 'compute#instance'},
        gce.GceError(status=400),
        {'kind': 'compute#unknown'},
        {},
    ]
    self.gce._get_parsers = get_mock_parsers
    results = self.gce._parse_list(resources)
    self.assertTrue(isinstance(results[0], OperationMock))
    self.assertTrue(isinstance(results[1], InstanceMock))
    self.assertTrue(results[2] is resources[2])
    self.assertTrue(isinstance(results[3], gce.GceError))
    self.assertTrue(isinstance(results[4], gce.GceError))

  def test_serialize_batch_api_reqeuest(self):
    base_path = '/compute/v1beta12/projects'
    request = gce_base.GoogleComputeEngineBase.API_REQUEST(
        'DELETE', 'my-project/instances/my-instance', None, None)
    self.assertEqual(
        'DELETE /compute/v1beta12/projects/my-project/instances/my-instance\n',
        self.gce._serialize_batch_api_request(base_path, request))

    request = gce_base.GoogleComputeEngineBase.API_REQUEST(
        'POST', 'my-project/instances', None, '{"kind": "compute#instance"}')
    self.assertEqual(
        'POST /compute/v1beta12/projects/my-project/instances\n'
        'Content-Type: application/json\n'
        'Content-Length: 28\n\n'
        '{"kind": "compute#instance"}',
        self.gce._serialize_batch_api_request(base_path, request))

    # Full path - used by the wait_for_list functionality.
    request = gce_base.GoogleComputeEngineBase.API_REQUEST(
        'GET',
        'https://www.googleapis.com/compute/v1beta12/projects/my-project/'
        'operations/operation-1234567890', None, None)
    self.assertEqual(
        'GET /compute/v1beta12/projects/my-project/operations/'
        'operation-1234567890\n',
        self.gce._serialize_batch_api_request(base_path, request))

  def test_parse_batch_api_response(self):
    response = (
        'HTTP/1.1 200 OK\n'
        'Content-Type: application/json; charset=UTF-8\n'
        'Content-Length: 51\n\n'
        '{"kind": "compute#instance", "name": "my-instance"}')
    parsed = self.gce._parse_batch_api_response(response)

    self.assertTrue(
        isinstance(parsed, gce_base.GoogleComputeEngineBase.BATCH_RESPONSE))
    self.assertEqual(200, parsed.response.status)
    self.assertEqual('OK', parsed.response.reason)
    self.assertEqual(
        '{"kind": "compute#instance", "name": "my-instance"}',
        parsed.body)

  def test_send_batch_request_too_many(self):
    request = gce_base.GoogleComputeEngineBase.API_REQUEST(
        'GET', 'my-project/instances/my-instance', None, None)
    self.assertRaises(ValueError,
                      self.gce._send_batch_request,
                      ([request] * (gce_base.MAX_BATCH_SIZE + 1)))

  def test_send_batch_request(self):
    def parse_headers(headers):
      header_dict = {}
      for header in headers.split('\n'):
        if not header: continue
        name, value = header.split(': ', 1)
        header_dict[name] = value
      return header_dict

    def mock_send_request(path, method, body, content_type):
      self.assertEqual('POST', method)
      self.assertEqual('https://www.googleapis.com/batch', path)
      match = re.match('multipart/mixed; boundary="([^\"]+)"', content_type)
      self.assertTrue(match)
      parts = body.split('--{0}'.format(match.group(1)))
      self.assertEqual(gce_base.MAX_BATCH_SIZE + 2, len(parts))
      self.assertEqual('', parts[0])
      self.assertEqual('--', parts[-1])
      parts = parts[1:-1]

      responses = []
      for part in parts:
        headers, payload = part.split('\n\n', 1)
        headers = parse_headers(headers)
        self.assertEqual('application/http', headers['Content-Type'])
        content_id = headers['Content-ID']
        self.assertTrue(content_id.startswith('<') and content_id.endswith('>'))
        content_id = content_id[1:-1]

        http_headers = payload.split('\n\n', 1)[0]
        split = http_headers.split('\n', 1)  # Try to split off the http command
        http_request = split[0]
        if len(split) > 1:
          headers = parse_headers(split[1])

        verb, path = http_request.split(' ')
        self.assertEqual('GET', verb)

        name = re.match('.*/([^/]+)', path).group(1)
        payload = '{{ "kind": "compute#instance", "name": "{0}" }}'.format(name)

        msg = MIMENonMultipart('application', 'http')
        msg.add_header('Content-ID', '<response-{0}>'.format(content_id))
        msg.set_payload(
            'HTTP/1.1 200 OK\n'
            'Content-Type: application/json; charset=UTF-8\n'
            'Content-Length: {0}\n\n'
            '{1}'.format(len(payload), payload))
        responses.append(msg)

      random.shuffle(responses)
      response = gce_base._BatchApiRequest()
      for r in responses:
        response.attach(r)

      response_string = response.as_string()
      boundary = response.get_boundary()
      response = httplib2.Response({
          'content-type': 'multipart/mixed; boundary="{0}"'.format(boundary),
          'status': 200,
          'reason': 'OK'})

      return response, response_string

    self.gce._send_request = mock_send_request
    requests = [
        gce_base.GoogleComputeEngineBase.API_REQUEST(
            'GET', 'my-project/instances/my-instance-{0}'.format(i), None, None)
        for i in xrange(gce_base.MAX_BATCH_SIZE)]

    responses = self.gce._send_batch_request(requests)
    self.assertEqual(gce_base.MAX_BATCH_SIZE, len(responses))

    for i, response in enumerate(responses):
      self.assertTrue(isinstance(
          response, gce_base.GoogleComputeEngineBase.BATCH_RESPONSE))
      self.assertEqual(200, response.response.status)
      self.assertEqual('OK', response.response.reason)

      instance = json.loads(response.body)
      self.assertEqual('my-instance-{0}'.format(i), instance['name'])
      self.assertEqual('compute#instance', instance['kind'])

  def test_execute_batch_request_big(self):
    def mock_send_batch_request(batch):
      self.assertTrue(len(batch) <= gce_base.MAX_BATCH_SIZE)
      responses = []
      for request in batch:
        response_body = '{{"kind": "compute#instance", "name": "{0}"}}'.format(
            re.match('.*/([^/]+)', request.url).group(1))
        responses.append(
            gce_base.GoogleComputeEngineBase.BATCH_RESPONSE(
                httplib2.Response({
                    'content-type': 'application/json',
                    'status': 200,
                    'reason': 'OK'}),
                response_body))
      return responses

    self.gce._send_batch_request = mock_send_batch_request

    requests_count = int(2.5 * gce_base.MAX_BATCH_SIZE)
    requests = [
        gce_base.GoogleComputeEngineBase.API_REQUEST(
            'GET', 'my-project/instandes/my-instance-{0}'.format(i), None, None)
        for i in xrange(requests_count)]

    responses = self.gce._execute_batch_request(requests)
    self.assertEqual(requests_count, len(responses))
    for i, response in enumerate(responses):
      instance = json.loads(response.body)
      self.assertTrue('my-instance-{0}'.format(i), instance['name'])

  def test_execute_batch_request_auth(self):
    retry_count = [0]  # Mutable closure

    class MockCredentials(object):
      def __init__(self):
        self.refresh_called = 0

      def refresh(self, unused_http):
        self.refresh_called += 1

    def mock_send_batch_request(batch):
      def validate_pass(unused_i):
        return True

      def validate_fail(i):
        # Fail every other request
        return (i % 2) == 0

      if retry_count[0] == 0:
        validate = validate_fail
      elif retry_count[0] == 1:
        validate = validate_pass
      else:
        self.fail('Shoud not retry more than 1x')

      retry_count[0] += 1

      # Process requests, validating credentials.
      responses = []
      for i, request in enumerate(batch):
        if validate(i):
          http_body = '{{"kind": "compute#instance", "name": "{0}"}}'.format(
              re.match('.*/([^/]+)', request.url).group(1))
          http_response = httplib2.Response({
              'content-type': 'application/json',
              'status': 200,
              'reason': 'OK'})
        else:
          http_body = '{"error": "Invalid credentials"}'
          http_response = httplib2.Response({
              'content-type': 'application/json',
              'status': 401,
              'reason': 'Invalid Credentials'
              })

        responses.append(gce_base.GoogleComputeEngineBase.BATCH_RESPONSE(
            http_response, http_body))

      return responses

    credentials = MockCredentials()
    gce = gce_base.GoogleComputeEngineBase(
        credentials,
        base_url='https://www.googleapis.com/compute/v1/projects/')

    gce._send_batch_request = mock_send_batch_request

    requests_count = 100
    requests = [
        gce_base.GoogleComputeEngineBase.API_REQUEST(
            'GET', 'my-project/instandes/my-instance-{0}'.format(i), None, None)
        for i in xrange(requests_count)]

    responses = gce._execute_batch_request(requests)
    self.assertEqual(requests_count, len(responses))
    for i, response in enumerate(responses):
      instance = json.loads(response.body)
      self.assertTrue('my-instance-{0}'.format(i), instance['name'])

    self.assertEqual(1, credentials.refresh_called)

  def test_wait_for_list(self):
    def mock_sleep(unused_seconds):
      pass

    def mock_execute_batch_request(requests):
      def complete(i):
        return i % 2 == 0  # Half of operations complete every turn.

      responses = []
      for i, request in enumerate(requests):
        self.assertFalse(request.body)

        status = 200
        reason = 'OK'
        body = ''

        if complete(i):
          info = re.match('.*/([^/]+)', request.url).group(1)
          if info == 'valid':
            body = {
                'kind': 'compute#operation',
                'status': 'DONE',
                'targetLink': ('https://www.googleapis.com/compute/v1/'
                               'projects/my-p/instances/instance')
                }
          elif info == 'error':
            body = {
                'kind': 'compute#operation',
                'status': 'DONE',
                'error': 'Error',
                'httpErrorStatusCode': 404,
                'error': {
                    'errors': [
                        {'message': 'Resource was not found.'}
                     ]
                  }
                }
          elif info == 'httperror':
            status = 404
            reason = 'Not Found'
            body = {'error': 'Not Found'}
          elif info == 'nobody':
            pass
          elif info == 'badjson':
            body = 'this is not json'
          elif info == 'noselflink':
            body = {'kind': 'compute#operation'}
          elif info == 'nokind':
            body = {}
          elif info == 'instance':
            body = {'kind': 'compute#instance', 'name': 'foo'}
          else:
            self.fail('Unexpected info {0}'.format(info))
        else:
          body = {
              'kind': 'compute#operation',
              'selfLink': '{0}'.format(request.url)
              }

        if isinstance(body, dict):
          body = json.dumps(body)

        response = httplib2.Response({'status': status})
        response.reason = reason
        responses.append(
            gce_base.GoogleComputeEngineBase.BATCH_RESPONSE(response, body))

      return responses

    # Only the selfLink is sent to the server so it encodes all states.
    operations = [
        {'selfLink': 'nokind'},
        {'kind': 'compute#operation', 'selfLink': 'valid'},
        {'kind': 'compute#operation', 'selfLink': 'error'},
        {'kind': 'compute#operation', 'selfLink': 'httperror'},
        {'kind': 'compute#operation', 'selfLink': 'nobody'},
        {'kind': 'compute#operation', 'selfLink': 'badjson'},
        {'kind': 'compute#operation', 'selfLink': 'noselflink'},
        {'kind': 'compute#operation', 'selfLink': 'nokind'},
    ]

    # Complete selfLinks to be URLs
    for o in operations:
      o['selfLink'] = ('https://www.googleapis.com/compute/v1/projects/my-p/'
                       'operations/' + o['selfLink'])
    operations = 100 * operations

    self.gce._execute_batch_request = mock_execute_batch_request
    self.gce._sleep = mock_sleep

    responses = self.gce._wait_for_list(operations)
    self.assertEqual(len(operations), len(responses))

    for operation, response in itertools.izip(operations, responses):
      info = re.match('.*/([^/]+)', operation['selfLink']).group(1)

      if info == 'valid':
        self.assertTrue(isinstance(response, dict))
        self.assertEqual('compute#instance', response['kind'])
      elif info == 'error':
        self.assertTrue(isinstance(response, gce.GceError))
        self.assertEqual(404, response.status)
        self.assertEqual('Resource was not found.', response.message)
      elif info == 'httperror':
        self.assertTrue(isinstance(response, gce.GceError))
        self.assertEqual(404, response.status)
        self.assertEqual('Not Found', response.message)
      elif info == 'nobody':
        self.assertTrue(isinstance(response, gce.GceError))
        self.assertEqual(400, response.status)
        self.assertEqual('Server returned an empty resource as a response.',
                         response.message)
      elif info == 'badjson':
        self.assertTrue(isinstance(response, gce.GceError))
        self.assertEqual(400, response.status)
        self.assertEqual(
            'Server returned invalid JSON response: this is not json',
            response.message)
      elif info == 'noselflink':
        self.assertTrue(isinstance(response, gce.GceError))
        self.assertEqual(400, response.status)
        self.assertTrue(response.message.startswith(
            'Operation resource is missing selfLink property'))
      elif info == 'nokind':
        self.assertTrue(isinstance(response, gce.GceError))
        self.assertEqual(400, response.status)
        self.assertTrue(response.message.startswith(
            'Server returned invalid resource'))
      else:
        self.fail('Unexpected info {0}'.format(info))

if __name__ == '__main__':
  unittest.main()
