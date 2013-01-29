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

"""Commands for interacting with Google Compute Engine persistent disks."""



import time


from google.apputils import appcommands
import gflags as flags

from gcutil import command_base
from gcutil import gcutil_logging

FLAGS = flags.FLAGS
LOGGER = gcutil_logging.LOGGER


class DiskCommand(command_base.GoogleComputeCommand):
  """Base command for working with the disks collection."""

  default_sort_field = 'name'
  summary_fields = (('name', 'name'),
                    ('description', 'description'),
                    ('zone', 'zone'),
                    ('status', 'status'),
                    ('source-snapshot', 'sourceSnapshot'),
                    ('size-gb', 'sizeGb'))

  detail_fields = (('name', 'name'),
                   ('description', 'description'),
                   ('creation-time', 'creationTimestamp'),
                   ('zone', 'zone'),
                   ('status', 'status'),
                   ('source-snapshot', 'sourceSnapshot'),
                   ('size-gb', 'sizeGb'))

  resource_collection_name = 'disks'

  def __init__(self, name, flag_values):
    super(DiskCommand, self).__init__(name, flag_values)

  def SetApi(self, api):
    """Set the Google Compute Engine API for the command.

    Args:
      api: The Google Compute Engine API used by this command.

    Returns:
      None.

    """
    self._disks_api = api.disks()
    self._zones_api = api.zones()


class AddDisk(DiskCommand):
  """Create new machine disks.

  More than one disk name can be specified. Multiple disks will be created in
  parallel.
  """

  positional_args = '<disk-name-1> ... <disk-name-n>'
  status_field = 'status'
  _TERMINAL_STATUS = ['READY', 'FAILED']

  def __init__(self, name, flag_values):
    super(AddDisk, self).__init__(name, flag_values)
    flags.DEFINE_string('description',
                        '',
                        'Disk description.',
                        flag_values=flag_values)
    flags.DEFINE_integer('size_gb',
                         None,
                         'The size of the persistent disk in GB.',
                         flag_values=flag_values)
    flags.DEFINE_string('zone',
                        None,
                        'The zone for this disk.',
                        flag_values=flag_values)
    flags.DEFINE_string('source_snapshot',
                        None,
                        'The source snapshot for this disk.',
                        flag_values=flag_values)
    flags.DEFINE_boolean('wait_until_complete',
                         False,
                         'Whether the program should wait until the disk'
                         ' is restored from snapshot.',
                         flag_values=flag_values)

  def Handle(self, *disk_names):
    """Add the specified disks.

    Args:
      *disk_names: The names of the disks to add.

    Returns:
      A tuple of (results, exceptions).

    Raises:
      CommandError: If the command is unsupported in this API version.
      UsageError: If no disk names are specified.
    """
    if not disk_names:
      raise app.UsageError('Please specify at lease one disk name.')

    self._flags.zone = self._GetZone(self._flags.zone)
    zone = self.NormalizeResourceName(
        self._project, 'zones', self._flags.zone)
    kind = self._GetResourceApiKind('disk')

    source_snapshot = None
    if self._flags.source_snapshot:
      source_snapshot = self.NormalizeResourceName(
          self._project,
          'snapshots',
          self._flags.source_snapshot)

    other_options = {}

    requests = []
    for name in disk_names:
      disk = {
          'kind': kind,
          'name': self._DenormalizeResourceName(name),
          'description': self._flags.description,
          'zone': zone,
          }

      if source_snapshot is not None:
        disk['sourceSnapshot'] = source_snapshot
      else:
        disk['sizeGb'] = self._flags.size_gb or 10
      requests.append(self._disks_api.insert(project=self._project,
                                             body=disk, **other_options))

    if self._flags.wait_until_complete and not self._flags.synchronous_mode:
      LOGGER.warn('wait_until_complete specified. Implying synchronous_mode.')
      self._flags.synchronous_mode = True

    (results, exceptions) = self.ExecuteRequests(requests)

    if self._flags.wait_until_complete:
      awaiting = results
      results = []
      for result in awaiting:
        if 'error' not in result:
          result = self._WaitUntilDiskIsComplete(result)
        results.append(result)

    list_type = 'diskList' if self._flags.synchronous_mode else 'operationList'
    return (self.MakeListResult(results, list_type), exceptions)

  def _InternalGetDisk(self, disk_name):
    """A simple implementation of getting current disk state.

    Args:
      disk_name: the name of the disk to get.

    Returns:
      Json containing full disk information.
    """
    disk_request = self._disks_api.get(
        project=self._project,
        disk=self._DenormalizeResourceName(disk_name))
    return disk_request.execute()

  def _WaitUntilDiskIsComplete(self, result):
    """Waits for the disk to complete.

    Periodically polls the server for current disk status. Exits if the
    status of the disk is READY or FAILED or the maximum waiting timeout
    has been reached. In both cases returns the last known disk details.

    Args:
      result: the current state of the disk.

    Returns:
      Json containing full disk information.
    """
    current_status = result[self.status_field]
    disk_name = result['name']
    start_time = time.time()
    LOGGER.info('Will wait for restore for: %d seconds.',
                self._flags.max_wait_time)
    while (time.time() - start_time < self._flags.max_wait_time and
           current_status not in self._TERMINAL_STATUS):
      LOGGER.info(
          'Waiting for disk. Current status: %s. Sleeping for %ss.',
          current_status, self._flags.sleep_between_polls)
      time.sleep(self._flags.sleep_between_polls)
      result = self._InternalGetDisk(disk_name)
      current_status = result[self.status_field]
    if current_status not in self._TERMINAL_STATUS:
      LOGGER.warn('Timeout reached. Disk %s has not yet been restored.',
                  disk_name)
    return result


class GetDisk(DiskCommand):
  """Get a machine disk."""

  positional_args = '<disk-name>'

  def __init__(self, name, flag_values):
    super(GetDisk, self).__init__(name, flag_values)

  def Handle(self, disk_name):
    """Get the specified disk.

    Args:
      disk_name: The name of the disk to get

    Returns:
      The result of getting the disk.
    """
    disk_request = self._disks_api.get(
        project='%s' % self._project,
        disk=self._DenormalizeResourceName(disk_name))

    return disk_request.execute()


class DeleteDisk(DiskCommand):
  """Delete one or more machine disks.

  If multiple disk names are specified, the disks will be deleted in parallel.
  """

  positional_args = '<disk-name-1> ... <disk-name-n>'
  safety_prompt = 'Delete disk'

  def __init__(self, name, flag_values):
    super(DeleteDisk, self).__init__(name, flag_values)

  def Handle(self, *disk_names):
    """Delete the specified disks.

    Args:
      *disk_names: The names of the disks to delete

    Returns:
      Tuple (results, exceptions) - result of deleting the disks.
    """
    requests = []
    for name in disk_names:
      requests.append(
          self._disks_api.delete(project=self._project,
                                 disk=self._DenormalizeResourceName(name)))
    results, exceptions = self.ExecuteRequests(requests)
    return (self.MakeListResult(results, 'operationList'), exceptions)


class ListDisks(DiskCommand):
  """List the machine disks for a project."""

  def Handle(self, page_size=None, page_token=None):
    """List the project's disks.

    Args:
      page_size: The size of the page to fetch.
      page_token: The next page token, as returned from the server.

    Returns:
      The result of listing the disks.
    """
    disk_request = self._disks_api.list(
        **self._BuildListArgs(page_size, page_token))
    return disk_request.execute()


def AddCommands():
  appcommands.AddCmd('adddisk', AddDisk)
  appcommands.AddCmd('getdisk', GetDisk)
  appcommands.AddCmd('deletedisk', DeleteDisk)
  appcommands.AddCmd('listdisks', ListDisks)
