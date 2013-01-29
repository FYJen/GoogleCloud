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

"""An interactive Google Compute Engine shell demo.

The interactive shell attempts to load default values from ~/.gce.config file
which has the following format:

[gce_config]
project: my-project
image: projects/google/images/ubuntu-12-04-v20120611
zone: us-east1-a
machine_type: n1-standard-1
network: default

"""

import code
import cStringIO
import inspect
import keyword
import logging
import optparse
import os
import platform
import re
import sys

from gcelib import gce
from gcelib import gce_util
from gcelib import shortcuts


# image and instance cause conflicts. Use 'img' for images instead of the
# default 'i' (which will be available for instances).
SHORTCUT_OVERRIDES = {
    'image': 'img',
    'images': 'img',
}


def create_help(commands, aliases):
  """Creates a help function bound to the installed commands.

  Args:
    commands: dict 'name' -> function, i.e.: 'insert_instance': insert_instance
    aliases: dict 'long_name' -> 'alias', i.e.: 'insert_instance': 'ii'

  Returns:
    A help function which will be available in the interactive mode as 'help'
  """

  # Platform dependent function to output select text in bold.
  # Disable bold printing on Windows.
  if platform.system() == 'Windows':

    def bold(out, msg):
      out.write(msg)
      return out
  else:
    reset_escape = '\033[0m'
    bold_escape = '\033[1m'

    def bold(out, msg):
      """Prints output in bold."""
      out.write(bold_escape)
      out.write(msg)
      out.write(reset_escape)
      return out

  def create_sort_key(name):
    """Creates a sort key from function name.

    When sorted, operations will be grouped object type (disk operations
    together, instance operatins together, etc.)

    Args:
      name: function name, i.e. 'insert_instance'

    Returns:
      sort key. A tuple of strings reordered such that the object type
      (instance) is first, i.e. ('instance', 'insert')
      If there is no underscore, returns 1-tuple
    """
    name = name.split('_')
    if len(name) > 1:
      return tuple(name[1:] + [name[0]])
    return (name,)

  def extract_doc(doc):
    """Extracts summary from the function doc string."""
    if not doc: return 'no information'
    end = doc.find('\n\n')
    if end > 0: doc = doc[:end]
    end = doc.find('.')
    if end > 0: doc = doc[:end + 1]
    doc = ' '.join(doc.split())
    if len(doc) > 100:
      doc = doc[:doc.rfind(' ', 0, 100)] + ' ...'
    return doc

  def global_help():
    """Prints global help for the interactive shell."""
    out = cStringIO.StringIO()
    bold(out, 'Google Compute Engine Client Help\n\n')
    bold(out, 'gce').write(': Instance of GoogleComputeEngine API Client.\n')
    bold(out, 'help(...)').write(': The help function\n\n')

    names = list(commands.keys())
    names.sort(key=create_sort_key)
    for name in names:
      method = commands[name]
      bold(out, method.func_name).write('(...)')
      short = aliases.get(name)
      if short:
        out.write('  ')
        bold(out, short)
      out.write('\n  - ')
      out.write(extract_doc(method.func_doc))
      out.write('\n')

    print out.getvalue()

  def command_help(function=None):
    """Prints help for the Google Compute Engine verb."""
    if function is None:
      return global_help()

    first = 0
    if not inspect.isfunction(function):
      if inspect.ismethod(function):
        function = function.im_func
        first = 1
      else:
        return help(function)

    out = cStringIO.StringIO()
    bold(out, function.func_name)
    out.write('(')

    argspec = inspect.getargspec(function)
    args = argspec.args[first:]

    indent = len(function.func_name) + 1
    new_line = out.tell() - indent
    for arg in xrange(len(args)):
      if arg > 0:
        out.write(', ')

      if arg < argspec.defaults:
        arg_text = '{0}={1}'.format(args[arg], repr(argspec.defaults[arg]))
      else:
        arg_text = args[arg]

      # Insert newline?
      if out.tell() - new_line + len(arg_text) > 70:
        out.write('\n' + indent * ' ')
        new_line = out.tell()
      out.write(arg_text)
    out.write(')\n')

    alias = aliases.get(function.func_name)
    if alias:
      out.write('\nAlias: ')
      bold(out, alias)
      out.write('\n')
    if function.func_doc:
      out.write('\n    ')
      out.write(function.func_doc)

    print out.getvalue()

  return command_help


def create_commands(options, api):
  """Creates the command dictionary for interactive mode."""

  def create_alias(name):
    """Creates a alias from the full function name."""
    split = name.split('_', 1)
    if len(split) > 1:
      verb, name = split
    else:
      verb, name = '', split[0]
    noun = SHORTCUT_OVERRIDES.get(name)
    if noun is None:
      noun = name.split('_')
      noun = ''.join([n[0] for n in noun])
    if verb not in ['list', 'all'] and name.endswith('s'):
      noun += 's'
    # Plural
    alias = verb[0] + noun
    if keyword.iskeyword(alias):
      alias += '_'
    return alias

  commands = {}

  # Add main commands.
  for name in dir(api):
    if name.startswith('_') or '_' not in name:
      continue
    func = getattr(api, name)
    if not inspect.ismethod(func):
      continue
    commands[name] = func

  # Create copy of commands dictionary for help.
  help_commands = dict(commands)

  command_aliases = {}
  if options.aliases:
    # Create aliases and keep track of their full names for duplicate detection.
    alias_to_full_names = {}  # dict alias -> list of full names
    for name, func in commands.iteritems():
      alias = create_alias(name)
      full_names = alias_to_full_names.get(alias)
      if full_names is None:
        alias_to_full_names[alias] = full_names = []
      full_names.append(name)

    # Build the aliases dictionary for help, add aliases to the commands dict.
    for alias, full_names in alias_to_full_names.iteritems():
      if len(full_names) == 1:
        name = full_names[0]
        command_aliases[name] = alias
        commands[alias] = commands[name]
      else:
        sys.stderr.write('Duplicate alias: {0} ({1})\n'.format(
            alias, ', '.join(full_names)))

  # Add shortcuts.
  for name in dir(shortcuts):
    if name.startswith('_') or name in commands:
      continue
    commands[name] = getattr(shortcuts, name)

  commands['help'] = create_help(help_commands, command_aliases)
  commands['gce'] = api

  # Add the config file-creation function.
  commands['config'] = get_build_config_fn(api)
  return commands


def get_build_config_fn(api):
  """Returns a function bound to api that creates a configuration file."""

  def build_config():
    """Launches an interaction to create a configuration file."""
    config_path = gce_util.build_config(api)
    if config_path is not None:
      new_defaults = gce_util.get_defaults(config_path)
      api.default_image = new_defaults.image
      api.default_machine_type = new_defaults.machine_type
      api.default_network = new_defaults.network
      api.default_project = new_defaults.project
      api.default_zone = new_defaults.zone
      if config_path != gce_util.DEFAULT_GCE_CONFIG_FILE:
        print ('Be sure to pass in --config={0} next time you launch the '
               'shell.'.format(config_path))

  return build_config


def add_version_options(parser):
  """Adds API version options to the command line parser."""
  parser.add_option('-v', '--service_version', dest='service_version',
                    help=('Version of Google Compute Engine Api to use. '
                          '({0})'.format(', '.join(gce.VERSIONS))))

  for version in gce.VERSIONS:
    parser.add_option(
        '--{0}'.format(version),
        action='store_const', const=version, dest='service_version',
        help=('Use {0} version of the Google Compute Engine '
              'Api.'.format(version)))
    parser.set_default('service_version', gce.DEFAULT_VERSION)


def interact(options, command):
  title = ('Welcome to the Google Compute Engine Shell!\n'
           'You are interacting with the {0} version of the API.\n'
           'Type "help()" or "help(<command>)" for help; type "config()" to '
           'create a configuration file.').format(options.service_version)
  sys.ps1 = 'gce> '
  sys.ps2 = '.... '
  code.interact(title, local=command)


def main():
  # Create command line options parser.
  parser = optparse.OptionParser()
  parser.add_option('-p', '--project', dest='project',
                    help='Project to use', default=None)
  parser.add_option('-d', '--debug', action='store_true', dest='debug',
                    help='Run in debug mode.', default=False)
  parser.add_option('-a', '--aliases', action='store_true', dest='aliases',
                    help='Enable aliases.')
  parser.add_option('-n', '--noaliases', action='store_false',
                    dest='aliases', help='Disable aliases.')
  parser.add_option('--config',
                    dest='config_file', help='The configuration file to use.')
  parser.add_option('-t', '--trace_token', dest='trace_token',
                    help='A Google-provided token for tracing API calls.')
  parser.set_default('config_file', gce_util.DEFAULT_GCE_CONFIG_FILE)
  parser.set_default('aliases', None)
  add_version_options(parser)
  # Parse command line args.
  options, args = parser.parse_args()
  if options.aliases is None:
    options.aliases = sys.stdin.isatty() and not args

  # Load default settings from the given config file.
  defaults = gce_util.get_defaults(options.config_file)

  # Create an instance of the GoogleComputeEngine client.
  api = gce.get_api(
      gce_util.get_credentials(),
      logging_level=logging.DEBUG if options.debug else logging.ERROR,
      default_image=defaults.image,
      default_machine_type=defaults.machine_type,
      default_network=defaults.network,
      default_project=options.project or defaults.project,
      default_zone=defaults.zone,
      version=options.service_version,
      trace_token=options.trace_token)

  # Build the dictionary of commands (bound GCE API functions).
  commands = create_commands(options, api)
  if args:
    # execute the file provided
    execfile(args[0], commands, {})
  else:
    # Enter interactive mode.
    interact(options, commands)

if __name__ == '__main__':
  main()
