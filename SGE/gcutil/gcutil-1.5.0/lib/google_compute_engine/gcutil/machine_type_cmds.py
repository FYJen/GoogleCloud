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

"""Commands for interacting with Google Compute Engine machine types."""




from google.apputils import appcommands
import gflags as flags

from gcutil import command_base

FLAGS = flags.FLAGS



class MachineTypeCommand(command_base.GoogleComputeCommand):
  """Base command for working with the machine types collection."""

  default_sort_field = 'name'
  summary_fields = (('name', 'name'),
                    ('description', 'description'),
                    ('cpus', 'guestCpus'),
                    ('memory-mb', 'memoryMb'),
                    ('ephemeral-disk-size-gb', 'ephemeralDisks.diskGb'),
                    ('max-pds', 'maximumPersistentDisks'),
                    ('max-total-pd-size-gb', 'maximumPersistentDisksSizeGb'))

  detail_fields = (('name', 'name'),
                   ('description', 'description'),
                   ('creation-time', 'creationTimestamp'),
                   ('cpus', 'guestCpus'),
                   ('memory-mb', 'memoryMb'),
                   ('ephemeral-disk-size-gb', 'ephemeralDisks.diskGb'),
                   ('max-pds', 'maximumPersistentDisks'),
                   ('max-total-pd-size-gb',
                    'maximumPersistentDisksSizeGb'),
                   ('available-zones', 'availableZone'))

  resource_collection_name = 'machine_types'

  def __init__(self, name, flag_values):
    super(MachineTypeCommand, self).__init__(name, flag_values)

  def SetApi(self, api):
    """Set the Google Compute Engine API for the command.

    Args:
      api: The Google Compute Engine API used by this command.

    Returns:
      None.

    """
    self._machine_type_api = api.machineTypes()


class GetMachineType(MachineTypeCommand):
  """Get a machine type."""

  def __init__(self, name, flag_values):
    super(GetMachineType, self).__init__(name, flag_values)

  def Handle(self, machine_type_name):
    """Get the specified machine type.

    Args:
      machine_type_name: Name of the machine type to get.

    Returns:
      The result of getting the machine type.
    """
    machine_type_name = self._DenormalizeResourceName(machine_type_name)

    machine_request = self._machine_type_api.get(
        project=self._project,
        machineType=machine_type_name)

    return machine_request.execute()


class ListMachineTypes(MachineTypeCommand):
  """List the machine types."""

  def Handle(self, page_size=None, page_token=None):
    """Build a request to list the machine types.

    Args:
      page_size: The size of the page to fetch.
      page_token: The next page token, as returned from the server.

    Returns:
      The result of getting the machine type.
    """
    machine_request = self._machine_type_api.list(
        **self._BuildListArgs(page_size, page_token))
    return machine_request.execute()


def AddCommands():
  appcommands.AddCmd('getmachinetype', GetMachineType)
  appcommands.AddCmd('listmachinetypes', ListMachineTypes)
