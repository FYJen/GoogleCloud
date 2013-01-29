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

"""A set of convenience functions for using Google Compute Engine."""


def network(network_name=None, external_ip=None, use_access_config=True):
  """Constructs a list of network interfaces for an instance.

  Args:
    network_name: The name of the network resource.
    external_ip: An optional IPv4 address. One will be chosen if omitted.
    use_access_config: If false, the instance will have no external address.

  Returns:
    A list containing one network interface.
  """
  network_interface = {'network': network_name or 'default'}
  if use_access_config:
    access_config = {'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}
    if external_ip:
      access_config['natIP'] = external_ip
    network_interface['accessConfigs'] = [access_config]
  return [network_interface]


def rw_disks(disk_names):
  disks = []
  for disk_name in disk_names:
    disks.append({'mode': 'READ_WRITE',
                  'type': 'PERSISTENT',
                  'source': disk_name})
  return disks


def ro_disks(disk_names):
  disks = []
  for disk_name in disk_names:
    disks.append({'mode': 'READ_ONLY',
                  'type': 'PERSISTENT',
                  'source': disk_name})
  return disks


def service_accounts(scopes=None, email='default'):
  scopes = scopes or []
  return [{'scopes': scopes,
           'email': email}]


def metadata(dictionary):
  items = [{'key': key, 'value': value}
           for key, value in dictionary.iteritems()]
  return {'items': items}
