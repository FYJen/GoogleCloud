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

"""Commands for moving resources from one zone to another."""



import collections
import datetime
import json
import os
import textwrap

from google.apputils import app
from google.apputils import appcommands
import gflags as flags

from gcelib import gce
from gcelib import gce_util
from gcutil import command_base
from gcutil import gcutil_logging
from gcutil import utils
from gcutil import version

FLAGS = flags.FLAGS
LOGGER = gcutil_logging.LOGGER


class CommandBase(object):

  def __init__(self, api):
    self._api = api


class InstanceMigrator(CommandBase):
  """A command for migrating a set of instances to another zone."""

  def __init__(self, api):
    super(InstanceMigrator, self).__init__(api)

  def _confirm(self, instances_to_mv, instances_to_ignore, dest_zone):
    """Displays what is about to happen and prompts the user to proceed.

    Args:
      instances_to_mv: The instances that will be moved.
      instances_to_ignore: Instances that will not be moved because they're
        already in the destination zone.
      dest_zone: The destination zone.

    Returns:
      True if the user wants to proceed.
    """
    # Ensures that the parameters make sense.
    assert instances_to_mv, (
        'Cannot confirm move if there are no instances to move.')
    assert not [i for i in instances_to_mv if i['zone'].endswith(dest_zone)], (
        'Some instances in the move set are already in the destination zone.')
    assert ([i for i in instances_to_ignore if i['zone'].endswith(dest_zone)] ==
            instances_to_ignore), (
                'Not all instances in ignore set are in destination zone.')

    if instances_to_ignore:
      print 'These instances are already in {0} and will not be moved:'.format(
          dest_zone)
      print utils.list_strings(i['name'] for i in instances_to_ignore)

    print 'The following instances will be moved to {0}:'.format(dest_zone)
    print utils.list_strings(i['name'] for i in instances_to_mv)
    return utils.proceed()

  def _set_ips(self, instances, ip_addresses):
    """Clears the natIP field for instances without reserved addresses."""
    for instance in instances:
      for interface in instance['networkInterfaces']:
        for config in interface['accessConfigs']:
          if config['natIP'] not in ip_addresses:
            config['natIP'] = None

  def _check_disk_preconditions(self, instances):
    """Determines which instances have non-ephemeral disks.

    Migration of persistent disks are currently not supported since we
    have no snapshot support.

    Args:
      instances: The instance objects to move over.

    Returns:
      A set containing the instances with non-ephemeral disks.
    """
    instances_with_disks = set()
    for instance in instances:
      for disk in instance['disks']:
        if disk['type'] != 'EPHEMERAL':
          instances_with_disks.add(instance)
    return instances_with_disks

  def _check_destination_zone(self, dest_zone):
    """Raises an exception if the destination zone is not valid."""
    utils.simple_print('Checking destination zone...')
    try:
      self._api.get_zone(dest_zone)
    except gce.GceError:
      self._raise_command_error('Invalid destination zone: {0}', dest_zone)
    print 'Done.'

  def _partition(self, instances, dest_zone):
    """Partitions instances by zone.

    Args:
      instances: The instance resources to partition.
      dest_zone: The destination zone that will be used to partition
        instances.

    Returns:
      A tuple of lists where the first list is all instances not
      in the destination zone and the second a list of all
      instances in the destination zone.
    """
    not_in_dest = []
    in_dest = []
    for instance in instances:
      if instance['zone'].endswith(dest_zone):
        in_dest.append(instance)
      else:
        not_in_dest.append(instance)
    return not_in_dest, in_dest

  def _write_log(self, log_path, instances_to_mv, dest_zone):
    """Logs the instances that will be moved and the destination zone."""
    print 'Writing log...',
    print 'If this command fails, you can re-attempt this move using:'
    print '  gcutil moveinstances --continue={0}'.format(log_path)
    with open(log_path, 'w') as f:
      contents = {'version': version.__version__,
                  'dest_zone': dest_zone,
                  'instances': instances_to_mv}
      json.dump(contents, f)

  def _parse_log(self, log_path):
    """Loads the JSON contents of the file pointed to by log_path."""
    utils.simple_print('Parsing log file...')
    with open(log_path) as f:
      result = json.load(f)
      print 'Done.'
      return result

  def _generate_replay_log_path(self):
    """Generates a file path in the form ~/.gcutil.move.YYmmddHHMMSS."""
    timestamp = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
    return os.path.join(os.path.expanduser('~'), '.gcutil.migrate.' + timestamp)

  def _raise_command_error(self, text, *args, **kwargs):
    """Prints a new-line character, then raises a CommandError.

    Args:
      text: The format string of the error message.
      args: The args passed to the format string.
      kwargs: The keyword args passed to the format string.

    Raises:
      CommandError
    """
    print
    raise command_base.CommandError(text.format(*args, **kwargs))

  def __call__(self, args):
    """Entry point to the command.

    Based on the arguments (see Args section), this method will either start
    a new move or resume a previously-failed one.

    New moves will result in the creation of a replay log. If any
    failures happen, the replay log will not be deleted and
    instructions for resuming the move will be displayed to the user.

    Args:
      args: An object with attributes name_regexes and dest_zone OR
        replay_log_file. With the former set of args, a fresh move
        is invoked. With the latter, a previously failed move can be
        resumed. If specified, name_regexes should be a list of regular
        expressions describing the names of instances to move and dest_zone
        should be the name of the destination zone. replay_log_file
        should be the path to a log file that has recorded the the state of
        a previous invocation.
    """

    if args.name_regexes and args.dest_zone:
      self._move_for_the_first_time(args.name_regexes, args.dest_zone)
    elif args.replay_log_file:
      self._replay_log(args.replay_log_file)
    else:
      raise command_base.CommandError(
          'Expected either instance names and destination zone or replay log.')

  def _move_for_the_first_time(self, regexes, dest_zone):
    """Starts a fresh move."""
    self._check_destination_zone(dest_zone)

    utils.simple_print(
        'Retrieving instances matching: {0}...', ' '.join(regexes))
    filter_expr = utils.regexes_to_filter_expression(regexes)
    instances = [i.to_json() for i in
                 self._api.all_instances(filter=filter_expr)]
    if not instances:
      self._raise_command_error('No matching instances were found.')
    print 'Done.'

    utils.simple_print('Checking instances...')
    instances_to_mv, instances_to_ignore = self._partition(instances, dest_zone)
    if not instances_to_mv:
      self._raise_command_error(
          'All instances are already in the destination zone.')
    print 'Done.'

    utils.simple_print('Checking disk preconditions...')
    instances_with_disks = self._check_disk_preconditions(instances_to_mv)
    if instances_with_disks:
      self._raise_command_error(
          'Migration of disks is currently not supported. '
          'The following instances have disks:\n{0}',
          utils.list_strings(instances_with_disks))
    print 'Done.'

    log_path = self._generate_replay_log_path()
    self._write_log(log_path, instances_to_mv, dest_zone)

    self._delete_and_recreate_instances(
        instances_to_mv, instances_to_ignore, dest_zone)

    # We have succeeded, so it's safe to delete the log file.
    self._delete_log_file(log_path)

  def _delete_log_file(self, log_path):
    """Deletes the file pointed to by log_path."""
    utils.simple_print('Deleting log file...')
    os.remove(log_path)
    print 'Done.'

  def _delete_and_recreate_instances(
      self, instances_to_mv, instances_to_ignore, dest_zone):
    """Deletes instances_to_mv and re-creates them in dest_zone.

    Args:
      instances_to_mv: The instances to delete and recreated in dest_zone.
      dest_zone: The destination zone.

    Raises:
      CommandError: If either the deletion or the insertion of instances
        fails or if the user aborts the move.
    """
    if not self._confirm(instances_to_mv, instances_to_ignore, dest_zone):
      self._raise_command_error('Move aborted.')

    utils.simple_print('Deleting instances...')
    res = self._api.delete_instances(instances_to_mv)
    errors = sorted(set(r.message for r in res
                        if isinstance(r, gce.GceError) and r.status != 404))
    if errors:
      raise command_base.CommandError(
          'Aborting due to errors while deleting instances:\n{0}'.format(
              utils.list_strings(errors)))
    print 'Done.'

    utils.simple_print('Clearing unreserved IP addresses...')
    ip_addresses = set(self._api.get_project().externalIpAddresses or [])
    self._set_ips(instances_to_mv, ip_addresses)
    print 'Done.'

    utils.simple_print('Recreating instances in {0}...', dest_zone)
    res = self._api.insert_instances(instances_to_mv, zone=dest_zone)
    errors = sorted(set(r.message for r in res if isinstance(r, gce.GceError)))
    if errors:
      raise command_base.CommandError(
          'Aborting due to errors while creating instances:\n{0}'.format(
              utils.list_strings(errors)))
    LOGGER.debug('Insert results: %s', res)
    print 'Done.'

  def _intersect(self, instances1, instances2):
    """set(instances1) & set(instances2) based on the name field."""
    names1 = set(i['name'] for i in instances1)
    return [i for i in instances2 if i['name'] in names1]

  def _subtract(self, instances1, instances2):
    """set(instances1) - set(instances2) based on the name field."""
    names2 = set(i['name'] for i in instances2)
    return [i for i in instances1 if i['name'] not in names2]

  def _replay_log(self, log_path):
    """Replays a previous move.

    This method first checks the current state of the project to see
    which instances have already been moved before moving the
    instances that were left behind in a previous failed move.

    The user is prompted to continue before any changes are made.

    Args:
      log_path: The path to the replay log.
    """
    if not os.path.exists(log_path):
      raise command_base.CommandError('File not found: {0}'.format(log_path))

    log = self._parse_log(log_path)
    dest_zone = log.get('dest_zone')
    if not dest_zone:
      raise command_base.CommandError(
          '{0} did not contain destination zone.'.format(log_path))
    print 'Destination zone is {0}.'.format(dest_zone)

    instances_to_mv = log.get('instances')

    instances_in_dest = [i.to_json() for i in self._api.all_instances(
        filter='zone eq .*{0}'.format(dest_zone))]

    # Note that we cannot use normal set intersection and subtraction
    # because two different instance resources could be referring to
    # the same instance (e.g., the instance was restarted by the
    # system).
    instances_to_ignore = self._intersect(instances_to_mv, instances_in_dest)
    instances_to_mv = self._subtract(instances_to_mv, instances_in_dest)

    if instances_to_mv:
      self._delete_and_recreate_instances(
          instances_to_mv, instances_to_ignore, dest_zone)
    else:
      print 'All instances have already been moved to their destination.'

    # We have succeeded, so it's safe to delete the log file.
    self._delete_log_file(log_path)


class InstanceMigratorAdapter(command_base.GoogleComputeCommand):
  """Move a set of instances to another zone.

  Multiple instance names or regular expressions can be specified. Any
  matching instance that's currently in the destination zone will be
  ignored. This command will fail if any of the instances have disks
  attached since there is currenly no way to move disks from one
  zone to another.
  """

  positional_args = '<name-regex-1> ... <name-regex-n> <destination-zone>'

  has_varargs = True

  def __init__(self, name, flag_values):
    super(InstanceMigratorAdapter, self).__init__(name, flag_values)

    flags.DEFINE_string(
        'continue',
        None,
        textwrap.dedent("""\
            A failed invocation of this subcommand will leave behind a
            log file that can be used to continue the move. This flag
            can be used to specify the path to the log file."""),
        flag_values=flag_values)

  def RunCommand(self, argv):
    if not FLAGS['continue'].value and len(argv) < 2:
      raise app.UsageError(
          'You must specify at least one instance and a destination zone.')

    if FLAGS['continue'].value and argv:
      raise app.UsageError(
          'You cannot specify instances or a destination zone when continuing '
          'a failed move.')

    credentials = gce_util.get_credentials()
    api = gce.get_api(
        credentials,
        version=FLAGS.service_version,
        default_project=FLAGS.project)

    if not FLAGS['continue'].value:
      name_regexes = argv[:-1]
      dest_zone = argv[-1]
    else:
      name_regexes = None
      dest_zone = None
    args = collections.namedtuple(
        'Namespace', ['name_regexes', 'dest_zone', 'replay_log_file'])(
            name_regexes, dest_zone, FLAGS['continue'].value)
    InstanceMigrator(api)(args)
    return True


def AddCommands():
  appcommands.AddCmd('moveinstances', InstanceMigratorAdapter)
