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

"""Mock Google Compute Engine API used for unit tests."""





class CommandExecutor(object):
  """An object to represent an apiclient endpoint with a fixed response."""

  def __init__(self, response):
    """Create a new CommandExecutor to return response for each API call."""
    self._response = response

  def __call__(self, **unused_kw):
    """Handle calling this object (part 1 of making an apiclient call)."""
    return self

  def execute(self):
    """Return the stored results for this API call (part 2 of apiclient)."""
    return self._response


class MockRequest(object):
  """Mock request type for use with the MockApi class."""

  def __init__(self, result):
    self.result = result

  def execute(self, http=None):  # pylint: disable-msg=W0613
    return self.result


class MockApiBase(object):
  """Base class for all mock APIs."""

  def __init__(self):
    self.requests = []

  def RegisterRequest(self, request_data):
    request = MockRequest(request_data)
    self.requests.append(request)
    return request


class MockDisksApi(MockApiBase):
  """Mock return result of the MockApi.disks() method."""

  def get(self, project='wrong_project', disk='wrong_disk'):
    return self.RegisterRequest({'project': project, 'disk': disk})

  def insert(self, project='wrong_project', body='wrong_disk_resource',
             sourceImage='wrong_source_image'):
    return self.RegisterRequest({'project': project, 'body': body,
                                 'sourceImage': sourceImage})

  def delete(self, project='wrong_project', disk='wrong_disk'):
    return self.RegisterRequest({'project': project, 'disk': disk})

  def list(self, project='wrong_project'):
    return self.RegisterRequest({'project': project})


class MockFirewallsApi(MockApiBase):
  """Mock return result of the MockApi.firewalls() method."""

  def get(self, project='wrong_project', firewall='wrong_firewall'):
    return self.RegisterRequest({'project': project, 'firewall': firewall})

  def insert(self, project='wrong_project', body='wrong_firewall_resource'):
    return self.RegisterRequest({'project': project, 'body': body})

  def delete(self, project='wrong_project', firewall='wrong_firewall'):
    return self.RegisterRequest({'project': project, 'firewall': firewall})

  def list(self, project='wrong_project'):
    return self.RegisterRequest({'project': project})


class MockNetworksApi(MockApiBase):
  """Mock return result of the MockApi.networks() method."""

  def get(self, project='wrong_project', network='wrong_network'):
    return self.RegisterRequest({'project': project, 'network': network})

  def insert(self, project='wrong_project', body='wrong_network_resource'):
    return self.RegisterRequest({'project': project, 'body': body})

  def delete(self, project='wrong_project', network='wrong_network'):
    return self.RegisterRequest({'project': project, 'network': network})

  def list(self, project='wrong_project'):
    return self.RegisterRequest({'project': project})


class MockOperationsApi(MockApiBase):
  """Mock return result of the MockApi.operations() method."""

  def get(self, project='wrong_project', operation='wrong_operation'):
    return self.RegisterRequest({'project': project, 'operation': operation})

  def delete(self, project='wrong_project', operation='wrong_operation'):
    return self.RegisterRequest({'project': project, 'operation': operation})

  def list(self, project='wrong_project'):
    return self.RegisterRequest({'project': project})


class MockImagesApi(MockApiBase):
  """Mock return result of the MockApi.images() method."""

  def get(self, project='wrong_project', image='wrong_image'):
    return self.RegisterRequest({'project': project, 'image': image})

  def insert(self, project='wrong_project', body='wrong_image_resource'):
    return self.RegisterRequest({'project': project, 'body': body})

  def delete(self, project='wrong_project', image='wrong_image'):
    return self.RegisterRequest({'project': project, 'image': image})

  def list(self, project='wrong_project'):
    return self.RegisterRequest({'project': project})

  def deprecate(self, project='wrong_project', image='wrong_image',
                body='wrong_deprecation_resource'):
    return self.RegisterRequest({'project': project, 'image': image,
                                 'body': body})


class MockInstancesApi(MockApiBase):
  """Mock return result of the MockApi.instances() method."""

  def get(self, project='wrong_project', instance='wrong_instance'):
    return self.RegisterRequest({'project': project, 'instance': instance})

  def insert(self, project='wrong_project', body='wrong_instance_resource'):
    return self.RegisterRequest({'project': project, 'body': body})

  def delete(self, project='wrong_project', instance='wrong_instance'):
    return self.RegisterRequest({'project': project, 'instance': instance})

  def list(self, project='wrong_project'):
    return self.RegisterRequest({'project': project})

  def addAccessConfig(self, project='wrong_project', instance='wrong_instance',
                      network_interface='wrong_network_interface',
                      body='wrong_instance_resource'):
    return self.RegisterRequest({'project': project, 'instance': instance,
                                 'network_interface': network_interface,
                                 'body': body})

  def deleteAccessConfig(self, project='wrong_project',
                         instance='wrong_instance',
                         network_interface='wrong_network_interface',
                         access_config='wrong_access_config'):
    return self.RegisterRequest({'project': project, 'instance': instance,
                                 'network_interface': network_interface,
                                 'access_config': access_config})


class MockKernelsApi(MockApiBase):
  """Mock return result of the MockApi.kernels() method."""

  def get(self, project='wrong_project', kernel='wrong_kernel'):
    return self.RegisterRequest({'project': project, 'kernel': kernel})

  def list(self, project='wrong_project'):
    return self.RegisterRequest({'project': project})


class MockMachineSpecsApi(MockApiBase):
  """Mock return result of the MockApi.machineSpecs() method."""

  def get(self, machineSpec='wrong_machine_type'):
    return self.RegisterRequest({'machineSpec': machineSpec})

  def list(self):
    return self.RegisterRequest('empty_result')


class MockMachineTypesApi(MockApiBase):
  """Mock return result of the MockApi.machineTypes() method."""

  def get(self, machineType='wrong_machine_type', **unused_kwargs):
    return self.RegisterRequest({'machineType': machineType})

  def list(self, **unused_kwargs):
    return self.RegisterRequest('empty_result')


class MockProjectsApi(MockApiBase):
  """Mock return result of the MockApi.projects() method."""

  def get(self, project='wrong_project'):
    return self.RegisterRequest({'project': project})

  def setCommonInstanceMetadata(self, project='wrong_project', body=None):
    return self.RegisterRequest({'project': project,
                                 'commonInstanceMetadata': body})


class MockSnapshotsApi(MockApiBase):
  """Mock return result of the MockApi.snapshots() method."""

  def get(self, project='wrong_project', snapshot='wrong_snapshot'):
    return self.RegisterRequest({'project': project, 'snapshot': snapshot})

  def insert(self, project='wrong_project', body='wrong_snapshot_resource'):
    return self.RegisterRequest({'project': project, 'body': body})

  def delete(self, project='wrong_project', snapshot='wrong_snapshot'):
    return self.RegisterRequest({'project': project, 'snapshot': snapshot})

  def list(self, project='wrong_project'):
    return self.RegisterRequest({'project': project})


class MockZonesApi(MockApiBase):
  """Mock return result of the MockApi.zones() method."""

  def get(self, zone='wrong_zone', **unused_kwargs):
    return self.RegisterRequest({'zone': zone})

  def list(self, **unused_kwargs):
    return self.RegisterRequest('empty_result')


class MockApi(object):
  """Mock of the Google Compute Engine API returned by the discovery client."""

  def disks(self):
    return MockDisksApi()

  def firewalls(self):
    return MockFirewallsApi()

  def networks(self):
    return MockNetworksApi()

  def images(self):
    return MockImagesApi()

  def instances(self):
    return MockInstancesApi()

  def kernels(self):
    return MockKernelsApi()

  def machineSpecs(self):
    return MockMachineSpecsApi()

  def machineTypes(self):
    return MockMachineTypesApi()

  def projects(self):
    return MockProjectsApi()

  def operations(self):
    return MockOperationsApi()

  def snapshots(self):
    return MockSnapshotsApi()

  def zones(self):
    return MockZonesApi()


class MockOutput(object):
  """Mock class used for capturing standard output in tests."""

  def __init__(self):
    self._capture_text = ''

  # Purposefully name this 'write' to mock an output stream
  # pylint: disable-msg=C6409
  def write(self, text):
    self._capture_text += text

  # Purposefully name this 'flush' to mock an output stream
  # pylint: disable-msg=C6409
  def flush(self):
    pass

  def GetCapturedText(self):
    return self._capture_text


class MockInput(object):
  """Mock class for standard input in tests."""

  def __init__(self, input_string):
    self._input_string = input_string

  # Purposefully name this 'readline' to mock an input stream
  # pylint: disable-msg=C6409
  def readline(self):
    return self._input_string


class MockCredential(object):
  """A mock credential that does nothing."""

  def authorize(self, http):
    return http
