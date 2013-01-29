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

"""Base command types for interacting with Google Compute Engine."""



import datetime
import httplib
import inspect
import json
import os
import re
import sys
import time
import traceback


from apiclient import discovery
from apiclient import errors
from apiclient import model
import httplib2
import iso8601
import oauth2client.client as oauth2_client

from google.apputils import app
from google.apputils import appcommands
import gflags as flags

from gcutil import auth_helper
from gcutil import flags_cache
from gcutil import gcutil_logging
from gcutil import metadata_lib
from gcutil import scopes
from gcutil import thread_pool
from gcutil import version
from gcutil import table_formatter

FLAGS = flags.FLAGS
LOGGER = gcutil_logging.LOGGER
CLIENT_ID = 'google-api-client-python-compute-cmdline/1.0'

CURRENT_VERSION = version.__default_api_version__
SUPPORTED_VERSIONS = version.__supported_api_versions__

# The maximum page size supported by the API for each list call.
MAX_PAGE_SIZE = 100


flags.DEFINE_enum(
    'service_version',
    CURRENT_VERSION,
    SUPPORTED_VERSIONS,
    'Google computation service version.')
flags.DEFINE_string(
    'api_host',
    'https://www.googleapis.com/',
    'API host name')
flags.DEFINE_string(
    'project',
    None,
    'The name of the Google Compute Engine project.')
flags.DEFINE_string(
    'project_id',
    None,
    'The name of the Google Compute Engine project. '
    'Deprecated, use --project instead.')
flags.DEFINE_bool(
    'print_json',
    False,
    'Output JSON instead of tabular format. Deprecated, use --format=json.')
flags.DEFINE_enum(
    'format', 'table',
    ('table', 'sparse', 'json', 'csv', 'names'),
    'Format for command output. Options include:'
    '\n table: formatted table output'
    '\n sparse: simpler table output'
    '\n json: raw json output (formerly --print_json)'
    '\n csv: csv format with header'
    '\n names: list of resource names only, no header')
flags.DEFINE_enum(
    'long_values_display_format',
    'elided',
    ['elided', 'full'],
    'The display preference for long table values.')
flags.DEFINE_bool(
    'fetch_discovery',
    False,
    'If true, grab the API description from the discovery API.')
flags.DEFINE_bool(
    'synchronous_mode',
    True,
    'If false, return immediately after posting a request.')
flags.DEFINE_integer(
    'sleep_between_polls',
    3,
    'The time to sleep between polls to the server in seconds.',
    1, 600)
flags.DEFINE_integer(
    'max_wait_time',
    120,
    'The maximum time to wait for an asynchronous operation to complete in '
    'seconds.',
    30, 1200)
flags.DEFINE_string(
    'trace_token',
    None,
    'Trace the API requests using a trace token provided by Google.')
flags.DEFINE_integer(
    'concurrent_operations',
    10,
    'The maximum number of concurrent operations to have in progress at once. '
    'Increasing this number will probably result in hitting rate limits.',
    1, 20)


class Error(Exception):
  """The base class for this tool's error reporting infrastructure."""


class CommandError(Error):
  """Raised when a command hits a general error."""


# A wrapper around an Api that adds a trace keyword to the Api.
class TracedApi(object):
  """Wrap an Api to add a trace keyword argument."""

  def __init__(self, obj, trace_token):
    def Wrap(func):
      def _Wrapped(*args, **kwargs):
        # Add a trace= URL parameter to the method call.
        if trace_token:
          kwargs['trace'] = trace_token
        return func(*args, **kwargs)
      return _Wrapped

    # Find all public methods and interpose them.
    for method in inspect.getmembers(obj, (inspect.ismethod)):
      if not method[0].startswith('__'):
        setattr(self, method[0], Wrap(method[1]))


class TracedComputeApi(object):
  """Wrap a ComputeApi object to return TracedApis."""

  def __init__(self, obj, trace_token):
    def Wrap(func):
      def _Wrapped(*args, **kwargs):
        ret = func(*args, **kwargs)
        if ret:
          ret = TracedApi(ret, trace_token)
        return ret
      return _Wrapped

    # Find all our public methods and interpose them.
    for method in inspect.getmembers(obj, (inspect.ismethod)):
      if not method[0].startswith('__'):
        setattr(self, method[0], Wrap(method[1]))


class ApiThreadPoolOperation(thread_pool.Operation):
  """A Thread pool operation that will execute an API request.

  This will wait for the operation to complete, if appropriate.  The
  result from the object will be the last operation object returned.
  """

  def __init__(self, request, command, wait_for_operation):
    """Initializer."""
    super(ApiThreadPoolOperation, self).__init__()
    self._request = request
    self._command = command
    self._wait_for_operation = wait_for_operation

  def Run(self):
    """Execute the request on a separate thread."""
    # Note that the httplib2.Http command isn't thread safe.  As such,
    # we need to create a new Http object here.
    http = self._command.CreateHttp()
    result = self._request.execute(http=http)
    if self._wait_for_operation:
      result = self._command.WaitForOperation(
          self._command.GetFlags(), time, result, http)
    return result


class GoogleComputeCommand(appcommands.Cmd):
  """Base class for commands that interact with the Google Compute Engine API.

  Overriding classes must override the SetApi and Handle methods.

  Attributes:
    GOOGLE_PROJECT_PATH: The common 'google' project used for storage of shared
        images and kernels.
    operation_detail_fields: A set of tuples of (json field name, human
        readable name) used to generate a pretty-printed detailed description
        of an operation resource.
    supported_versions: The list of API versions supported by this tool.
    safety_prompt: A boolean indicating whether the command requires user
        confirmation prior to executing.
  """

  GOOGLE_PROJECT_PATH = 'projects/google'

  operation_default_sort_field = 'insertTime'
  operation_summary_fields = (('name', 'name'),
                              ('status', 'status'),
                              ('status-message', 'statusMessage'),
                              ('target', 'targetLink'),
                              ('operation-type', 'operationType'),
                              ('error', 'error.errors.code'),
                              ('warning', 'warnings.code'))
  operation_detail_fields = (('name', 'name'),
                             ('creation-time', 'creationTimestamp'),
                             ('status', 'status'),
                             ('progress', 'progress'),
                             ('status-message', 'statusMessage'),
                             ('target', 'targetLink'),
                             ('target-id', 'targetId'),
                             ('client-operation-id', 'clientOperationId'),
                             ('insert-time', 'insertTime'),
                             ('user', 'user'),
                             ('start-time', 'startTime'),
                             ('end-time', 'endTime'),
                             ('operation-type', 'operationType'),
                             ('error-code', 'httpErrorStatusCode'),
                             ('error-message', 'httpErrorMessage'),
                             ('warning', 'warnings.code'),
                             ('warning-message', 'warnings.message'))

  # If this is set to True then the arguments and flags for this
  # command are sorted such that everything that looks like a flag is
  # pulled out of the arguments.  If a command needs unparsed flags
  # after positional arguments (like ssh) then set this to False.
  sort_args_and_flags = True

  def __init__(self, name, flag_values):
    """Initializes a new instance of a GoogleComputeCommand.

    Args:
      name: The name of the command.
      flag_values: The values of command line flags to be used by the command.
    """
    super(GoogleComputeCommand, self).__init__(name, flag_values)
    self._credential = None
    self.supported_versions = SUPPORTED_VERSIONS

    if hasattr(self, 'safety_prompt'):
      flags.DEFINE_bool('force',
                        False,
                        'Override the "%s" prompt' % self.safety_prompt,
                        flag_values=flag_values,
                        short_name='f')

    if self._IsListCommand():
      summary_fields = [x[0] for x in getattr(self, 'summary_fields', [])]
      if summary_fields:
        sort_fields = []
        for field in summary_fields:
          sort_fields.append(field)
          sort_fields.append('-' + field)

        flags.DEFINE_enum('sort_by',
                          None,
                          sort_fields,
                          'Sort output results by the given field name. Field '
                          'names starting with a "-" will lead to a descending '
                          'order.',
                          flag_values=flag_values)

      flags.DEFINE_integer('max_results',
                           100,
                           'Maximum number of items to list',
                           lower_bound=1,
                           flag_values=flag_values)
      flags.DEFINE_string('filter',
                          None,
                          'Filter expression for filtering listed resources. '
                          'See gcutil documentation for syntax of the filter '
                          'expression here: http://developers.google.com'
                          '/compute/docs/gcutil/tips#filtering',
                          flag_values=flag_values)
      flags.DEFINE_bool('fetch_all_pages',
                        False,
                        'Whether to fetch all pages on truncated results',
                        flag_values=flag_values)

  def _IsListCommand(self):
    """Determine whether this is a list command.

    Returns:
      True if this is a list command, False otherwise.
    """
    return self.__class__.__name__.startswith('List')

  def _BuildListArgs(self, page_size, page_token):
    """Builds args for the list method.

    Args:
      page_size: The maximum number of results that should be returned.
      page_token: The page token of the next page, as specified by the
        server.

    Returns:
      Dictionary of list method args.
    """
    d = {'project': self._project}
    if page_size:
      d['maxResults'] = min(MAX_PAGE_SIZE, page_size)
    if page_token:
      d['pageToken'] = page_token
    if self._flags.filter:
      d['filter'] = self._flags.filter
    return d

  def _ReadInSelectedItem(self, menu, menu_name):
    while True:
      userinput = raw_input('>>> ').strip()
      try:
        selection = int(userinput)
        if selection in menu:
          return selection
      except ValueError:
        pass
      print 'Invalid selection, please choose one of the listed ' + menu_name

  def _ListCollection(self, collection_api, project):
    """Lists all resources in the collection, getting all pages as necessary.

    Args:
      collection_api: A collection api that implements list method.
      project: A project whose resources should be listed.

    Returns:
      A list of resources from the collection.
    """
    request = collection_api.list(project=project)
    choices = []
    while True:
      result = request.execute()
      choices.extend(result.get('items', []))
      if not 'nextPageToken' in result:
        break
      request = collection_api.list(project=project,
                                    pageToken=result['nextPageToken'])
    return choices

  def _PromptForEntry(self, collection_api, collection_name, project=None,
                      auto_select=True, extract_resource_prompt=None):
    """Prompt the user to select an entry from an API collection.

    Args:
      collection_api: The API collection wrapper.
      collection_name: The name of the collection used in building the prompts.
      project: A project whose collection to use. Defaults to self._project.
      auto_select: If True and the collection has a single element then that
          element is chosen without prompting the user.
      extract_resource_prompt: A function that takes a resource JSON and returns
          the resource prompt. If not provided, the resource's 'name' field is
          going to be used as the default prompt text.

    Returns:
      A collection entry as selected by the user or None if the collection is
        empty;
    """
    choices = self._ListCollection(collection_api, project or self._project)
    return self._PromptForChoice(
        choices, collection_name, auto_select, extract_resource_prompt)

  def _PromptForChoice(self, choices, collection_name, auto_select=True,
                       extract_resource_prompt=None):
    """Prompts user to select one of the resources from the choices list.

    The function will create list of prompts from the list of choices. If caller
    passed extract_resource_prompt function, the extract_resource_prompt will be
    called on each resource to generate appropriate prompt text.

    Prompt strings are sorted alphabetically and offered to the user to select
    the desired option. The selected resource is then returned to the caller.

    If the list of choices is empty, None is returned.
    If there is only one available choice and auto_select is True, user is not
    prompted but rather, the only available option is returned.

    Args:
      choices: List of Google Compute Engine resources from which user should
        choose.
      collection_name: Name of the collection to present to the user.
      auto_select: Boolean. If set to True and only one resource is available in
        the list of choices, user will not be prompted but rather, the only
        available option will be chosen.
      extract_resource_prompt: Lambda resource -> string. If supplied, this
        function will be called on each resource to generate the prompt string
        for the resource.

    Returns:
      The resource user selected. Returns the actual resource as the JSON object
      model represented as Python dictionary.
    """
    if extract_resource_prompt is None:

      def ExtractResourcePrompt(resource):
        return resource['name'].split('/')[-1]

      extract_resource_prompt = ExtractResourcePrompt

    if not choices:
      return None

    if auto_select and len(choices) == 1:
      print 'Selecting the only available %s: %s' % (
          collection_name, choices[0]['name'])
      if 'deprecated' in choices[0]:
        LOGGER.warn('Warning: %s is deprecated!', choices[0]['name'])
      return choices[0]

    deprecated_choices = [(extract_resource_prompt(ch) + ' (DEPRECATED)', ch)
                          for ch in choices if 'deprecated' in ch
                          and ch['deprecated']['state'] == 'DEPRECATED']
    deprecated_choices.sort(key=lambda pair: pair[0])
    choices = [(extract_resource_prompt(ch), ch) for ch in choices
               if not 'deprecated' in ch]
    choices.sort(key=lambda pair: pair[0])
    choices.extend(deprecated_choices)

    for i, (short_name, unused_choice) in enumerate(choices):
      print '%d: %s' % (i + 1, short_name)

    selection = self._ReadInSelectedItem(
        range(1, len(choices) + 1), collection_name + 's')
    return choices[selection - 1][1]

  def _PromptForKernel(self):
    """Prompt the user to select a kernel from the available kernels.

    Returns:
      A kernel resource selected by the user, or None if no kernels available.
    """

    def ExtractKernelPrompt(kernel):
      return self._PresentElement(
          self.NormalizeResourceName('google', 'kernels', kernel['name']))

    return self._PromptForEntry(
        self._kernels_api, 'kernel', 'google',
        extract_resource_prompt=ExtractKernelPrompt)

  def _PromptForImage(self):
    choices = (self._ListCollection(self._images_api, 'google') +
               self._ListCollection(self._images_api, self._project))

    def ExtractImagePrompt(image):
      return self._PresentElement(image['selfLink'])

    return self._PromptForChoice(choices, 'image', True, ExtractImagePrompt)

  def _PromptForZone(self):
    """Prompt the user to select a zone from the current list.

    Returns:
      A zone resource as selected by the user.
    """
    now = datetime.datetime.utcnow()

    def ExtractZonePrompt(zone):
      """Creates a text prompt for a zone resource.

      Includes maintenance information for zones that enter maintenance in less
      than two weeks.

      Args:
        zone: The Google Compute Engine zone resource.

      Returns:
        string to represent a specific zone choice to present to the user.
      """
      name = zone['name'].split('/')[-1]
      maintenance = GoogleComputeCommand._GetNextMaintenanceStart(zone, now)
      if maintenance is not None:
        if maintenance < now:
          msg = 'currently in maintenance'
        else:
          delta = maintenance - now
          if delta >= datetime.timedelta(weeks=2):
            msg = None
          elif delta.days < 1:
            msg = 'maintenance starts in less than 24 hours'
          elif delta.days == 1:
            msg = 'maintenance starts in 1 day'
          else:
            msg = 'maintenance starts in %s days' % delta.days
        if msg:
          return '%s  (%s)' % (name, msg)
      return name

    return self._PromptForEntry(self._zones_api, 'zone',
                                extract_resource_prompt=ExtractZonePrompt)

  def _PromptForDisk(self):
    """Prompt the user to select a disk from the current list.

    Returns:
      A disk resource as selected by the user.
    """
    return self._PromptForEntry(self._disks_api, 'disk', auto_select=False)

  def _PromptForMachineType(self):
    """Prompt the user to select a machine type from the current list.

    Returns:
      A machine type resource as selected by the user.
    """
    return self._PromptForEntry(self._machine_types_api, 'machine type')

  @staticmethod
  def _GetNextMaintenanceStart(zone, now=None):
    def ParseDate(date):
      # Removes the timezone awareness from the timestamp we get back
      # from the server. This is necessary because utcnow() is
      # timezone unaware and it's much easier to remove timezone
      # awareness than to add it in. The latter option requires more
      # code and possibly other libraries.
      return iso8601.parse_date(date).replace(tzinfo=None)

    if now is None:
      now = datetime.datetime.utcnow()
    maintenance = zone.get('maintenanceWindows')
    next_window = None
    if maintenance:
      # Find the next maintenance window.
      for mw in maintenance:
        # Is it already past?
        end = mw.get('endTime')
        if end:
          end = ParseDate(end)
          if end < now:
            # Skip maintenance because it has occurred in the past.
            continue

        begin = mw.get('beginTime')
        if begin:
          begin = ParseDate(begin)
          if next_window is None or begin < next_window:
            next_window = begin
    return next_window

  def _GetZone(self, zone=None):
    """Notifies the user if the given zone will enter maintenance soon.

    The given zone can be None in which case the user is prompted for
    a zone. This method is intended to provide a warning to the user
    if he or she seeks to create a disk or instance in a zone that
    will enter maintenance in less than two weeks.

    Args:
      zone: The name of the zone chosen, or None.

    Returns:
      The given zone or the zone chosen through the prompt.
    """
    if zone is None:
      zone_resource = self._PromptForZone()
      zone = zone_resource['name']
    else:
      zone = zone.split('/')[-1]
      zone_resource = self._zones_api.get(
          project=self._project, zone=zone).execute()

      # Warns the user if there is an upcoming maintenance for the
      # chosen zone. Times returned from the server are in UTC.
      now = datetime.datetime.utcnow()
      next_win = GoogleComputeCommand._GetNextMaintenanceStart(
          zone_resource, now)
      if next_win is not None:
        if next_win < now:
          msg = 'is unavailable due to maintenance'
        else:
          delta = next_win - now
          if delta >= datetime.timedelta(weeks=2):
            msg = None
          elif delta.days < 1:
            msg = 'less than 24 hours'
          elif delta.days == 1:
            msg = '1 day'
          else:
            msg = '%s days' % delta.days
          if msg:
            msg = 'will become unavailable due to maintenance in %s' % msg
        if msg:
          LOGGER.warn('%s %s.', zone, msg)
    return zone

  def _AuthenticateWrapper(self, http):
    """Adds the OAuth token into http request.

    Args:
      http: An instance of httplib2.Http or something that acts like it.

    Returns:
      httplib2.Http like object.

    Raises:
      CommandError: If the credentials can't be found.
    """
    if not self._credential:
      self._credential = auth_helper.GetCredentialFromStore(
          self.__GetRequiredAuthScopes())
      if not self._credential:
        raise CommandError(
            'Could not get valid credentials for API.')
    return self._credential.authorize(http)


  def _ParseArgumentsAndFlags(self, flag_values, argv):
    """Parses the command line arguments for the command.

    This method matches up positional arguments based on the
    signature of the Handle method.  It also parses the flags
    found on the command line.

    argv will contain, <main python file>, positional-arguments, flags...

    Args:
      flag_values: The flags list to update
      argv: The command line argument list

    Returns:
      The list of position arguments for the given command.

    Raises:
      CommandError: If any problems occur with parsing the commands (e.g.,
          type mistmatches, out of bounds, unknown commands, ...).
    """
    # If we are sorting args and flags, kick the flag parser into gnu
    # mode and parse some more.  argv will be all of the unparsed args
    # after this.
    if self.sort_args_and_flags:
      try:
        old_gnu_mode = flag_values.IsGnuGetOpt()
        flag_values.UseGnuGetOpt(True)
        argv = flag_values(argv)
      except (flags.IllegalFlagValue, flags.UnrecognizedFlagError) as e:
        raise CommandError(e)
      finally:
        flag_values.UseGnuGetOpt(old_gnu_mode)

    # We use the same positional arguments used by the command's Handle method.
    # For AddDisk this will be, ['self', 'disk_name'].
    argspec = inspect.getargspec(self.Handle)

    # Skip the implicit argument 'self' and take the list of
    # positional command args.
    default_count = len(argspec.defaults) if argspec.defaults else 0
    pos_arg_names = argspec.args[1:]

    # We then parse off values for those positional arguments from argv.
    # Note that we skip the first argument, as that is the command path.
    pos_arg_values = argv[1:len(pos_arg_names) + 1]

    # Take all the arguments past the positional arguments. If there
    # is a var_arg on the command this will get passed in.
    unparsed_args = argv[len(pos_arg_names) + 1:]

    # If we did not get enough positional argument values print error and exit.
    if len(pos_arg_names) - default_count > len(pos_arg_values):
      missing_args = pos_arg_names[len(pos_arg_values):]
      missing_args = ['"%s"' % a for a in missing_args]
      raise CommandError('Positional argument %s is missing.' %
                         ', '.join(missing_args))

    # If users specified flags in place of positional argument values,
    # print error and exit.
    for (name, value) in zip(pos_arg_names, pos_arg_values):
      if value.startswith('--'):
        raise CommandError('Invalid positional argument value \'%s\' '
                           'for argument \'%s\'\n' % (value, name))

    # If there are any unparsed args and the command is not expecting
    # varargs, print error and exit.
    if (unparsed_args and

        #MOE_begin_strip
        # This is a temporary measure to allow new-style commands to
        # have varargs without having a Handle method.
        #MOE_end_strip
        not getattr(self, 'has_varargs', False) and

        not argspec.varargs):
      unparsed_args = ['"%s"' % a for a in unparsed_args]
      raise CommandError('Unknown argument: %s' %
                         ', '.join(unparsed_args))

    return argv[1:]

  def _BuildComputeApi(self, http):
    """Builds the Google Compute Engine API to use.

    Args:
      http: a httplib2.Http like object for communication.

    Returns:
      The API object to use.
    """
    # For versions of the apiclient library prior to v1beta2, we need to
    # specify the LoggingJsonModel in order to get request and response
    # logging to work.
    json_model = (model.LoggingJsonModel()
                  if 'LoggingJsonModel' in dir(model)
                  else model.JsonModel())
    if FLAGS.fetch_discovery:
      discovery_uri = (FLAGS.api_host +
                       'discovery/v1/apis/{api}/{apiVersion}/rest')
      return self.WrapApiIfNeeded(discovery.build(
          'compute',
          FLAGS.service_version,
          http=http,
          discoveryServiceUrl=discovery_uri,
          model=json_model))
    else:
      discovery_file_name = os.path.join(
          os.path.dirname(__file__),
          'compute/%s.json' % FLAGS.service_version)
      try:
        discovery_file = file(discovery_file_name, 'r')
        discovery_doc = discovery_file.read()
        discovery_file.close()
      except IOError:
        raise CommandError(
            'Could not load discovery document from disk. Perhaps try '
            '--fetch_discovery. \nFile: %s' % discovery_file_name)

      return self.WrapApiIfNeeded(discovery.build_from_document(
          discovery_doc,
          base=FLAGS.api_host,
          http=http,
          model=json_model))

  @staticmethod
  def WrapApiIfNeeded(api):
    """Wraps the API to enable logging or tracing."""
    if FLAGS.trace_token:
      return TracedComputeApi(api, 'token:%s' % (FLAGS.trace_token))
    return api

  @staticmethod
  def DenormalizeResourceName(project, collection_name, resource_name):
    """Return the relative name for the given resource.

    Args:
      project: The name of the project containing the resource.
      collection_name: The name of the collection containing the resource.
      resource_name: The name of the resource. This can be either relative
                     or absolute.
    Returns:
      The name of the resource relative to its enclosing collection.

    Raises:
      CommandError: If the name of the resource does not match the given
          project and/or collection.
    """
    resource_name = resource_name.strip('/')
    collection_prefix = 'projects/%s/%s/' % (project, collection_name)
    if '/' in resource_name and resource_name.startswith(collection_prefix):
      resource_name = resource_name[len(collection_prefix):]
    if '/' in resource_name:
      raise CommandError('Resource names cannot contain \'/\'')
    return resource_name

  @staticmethod
  def DenormalizeProjectName(flag_values):
    """Denormalize the 'project' entry in the given FlagValues instance.

    Args:
      flag_values: The FlagValues instance to update.

    Raises:
      CommandError: If the project is missing or malformed.
    """
    project = flag_values.project or flag_values.project_id

    if not project:
      raise CommandError(
          'You must specify a project name using the "--project" flag.')
    elif project.lower() != project:
      raise CommandError(
          'Characters in project name must be lowercase: %s.' % project)

    project = project.strip('/')
    if project.startswith('projects/'):
      project = project[len('projects/'):]
    if '/' in project:
      raise CommandError('Project names can contain a \'/\' only when they '
                         'begin with \'projects/\'.')

    flag_values.project = project
    flag_values.project_id = None

  def _GetBaseApiUrl(self):
    """Get the base API URL given the current flag_values.

    Returns:
      The base API URL.  For example,
      https://www.googleapis.com/compute/v1beta12.
    """
    return '%scompute/%s' % (self._flags.api_host, self._flags.service_version)

  def _AddBaseUrlIfNecessary(self, resource_path):
    """Add the base URL to a resource_path if required by the service_version.

    Args:
      resource_path: The resource path to add the URL to.

    Returns:
      A full API-usable reference to the given resource_path.
    """
    if not self._GetBaseApiUrl() in resource_path:
      return '%s/%s' % (self._GetBaseApiUrl(), resource_path)
    return resource_path

  def _StripBaseUrl(self, value):
    """Removes the a base URL from the string if it exists.

    Note that right now the server may not return exactly the right
    base URL so we strip off stuff that looks like a base URL.

    Args:
      value: The string to strip the base URL from.

    Returns:
      A string without the base URL.
    """
    pattern = '^' + re.escape(self._flags.api_host) + r'compute/\w*/'
    return re.sub(pattern, '', value)

  def NormalizeTopLevelResourceName(self, collection_name, resource_name):
    """Return the full name for the given resource.

    Args:
      collection_name: The name of the top-level collection containing the
                       resource.
      resource_name: The name of the resource. This can be either relative
                     to the collection or absolute.

    Returns:
      The full URL of the resource.
    """
    resource_name = resource_name.strip('/')
    if (resource_name.startswith(collection_name + '/') or
        resource_name.startswith(self._flags.api_host)):
      # This does not appear to be a relative name.
      absolute_name = resource_name
    else:
      absolute_name = '%s/%s' % (collection_name, resource_name)

    return self._AddBaseUrlIfNecessary(absolute_name)

  def NormalizeResourceName(self, project, collection_name,
                            resource_name):
    """Return the full name for the given resource.

    Args:
      project: The name of the project containing the resource.
      collection_name: The name of the collection containing the resource.
      resource_name: The name of the resource. This can be either relative
          or absolute.

    Returns:
      The full URL of the resource.
    """
    resource_name = resource_name.strip('/')

    if (collection_name == 'machine-types' and
        'v1beta13' in self.supported_versions and
        self._IsUsingAtLeastApiVersion('v1beta13')):
      collection_name = 'machineTypes'

    if (resource_name.startswith('projects/') or
        resource_name.startswith(collection_name + '/') or
        resource_name.startswith(self._flags.api_host)):
      # This does not appear to be a relative name.
      return self._AddBaseUrlIfNecessary(resource_name)

    return self.NormalizeTopLevelResourceName(
        'projects/%s/%s' % (project, collection_name),
        resource_name)

  def _DenormalizeResourceName(self, resource_name):
    """Return the relative name for the given resource.

    Relies on the command instance's flags and the presence of a
    resource_collection_name field containing the common collection name
    for the class.

    Args:
      resource_name: The name of the resource. This can be either relative
                     or absolute.

    Returns:
      The name of the resource relative to its enclosing collection.

    Raises:
      CommandError: If the name of the resource does not match the given
          project and/or collection.
    """
    resource_name = self._StripBaseUrl(resource_name)
    collection_name = self.resource_collection_name

    return self.DenormalizeResourceName(self._flags.project, collection_name,
                                        resource_name)

  def _HandleSafetyPrompt(self, positional_arguments):
    """If a safety prompt is present on the class, handle it now.

    By defining a field 'safety_prompt', derived classes can request
    that the user confirm a dangerous operation prior to execution,
    e.g. deleting a resource.  Users may override this check by
    passing the --force flag on the command line.

    Args:
      positional_arguments: A list of positional argument strings.

    Returns:
      True if the command should continue, False if not.
    """
    if hasattr(self, 'safety_prompt'):
      if not self._flags.force:
        prompt = self.safety_prompt
        if positional_arguments:
          prompt = '%s %s' % (prompt, ', '.join(positional_arguments))
        print '%s? [y/N]' % prompt
        userinput = raw_input('>>> ')

        if not userinput:
          userinput = 'n'
        userinput = userinput.lstrip()[:1].lower()

        if not userinput == 'y':
          return False

    return True

  def _IsUsingAtLeastApiVersion(self, required_version):
    """Determine if in-use API version is at least the specified version.

    Args:
      required_version: The API version to test.

    Returns:
      True if the given API version is equal or newer than the in-use
      API version, False otherwise.

    Raises:
      CommandError: If the specified API version is not known.
    """
    if not (required_version in self.supported_versions and
            self._flags.service_version in self.supported_versions):
      raise CommandError('API version %s/%s unknown' % (
          required_version, self._flags.service_version))

    for index, known_version in enumerate(self.supported_versions):
      if known_version == self._flags.service_version:
        current_index = index
      if known_version == required_version:
        given_index = index

    return current_index >= given_index

  def _GetResourceApiKind(self, resource):
    """Determine the API version driven resource 'kind'.

    Args:
      resource: The resource type to generate a 'kind' string for.

    Returns:
      A string containing the API 'kind'
    """
    return 'compute#%s' % resource

  def Run(self, argv):
    """Run the command, printing the result.

    Args:
      argv: The arguments to the command.

    Returns:
      0 if the command completes successfully, otherwise 1.
    """
    try:
      pos_arg_values = self._ParseArgumentsAndFlags(FLAGS, argv)
      gcutil_logging.SetupLogging()

      # Synchronize the flags with any cached values present.
      flags_cache_obj = flags_cache.FlagsCache()
      flags_cache_obj.SynchronizeFlags()


      self.SetFlagDefaults()
      self.DenormalizeProjectName(FLAGS)
      self.SetFlags(FLAGS)

      has_errors = self.RunCommand(pos_arg_values)

      # Updates the flags cache file only when the command exits with
      # a non-zero error code.
      if not has_errors:
        flags_cache_obj.UpdateCacheFile()

      return has_errors
    except errors.HttpError, http_error:
      self.LogHttpError(http_error)
      return 1
    except app.UsageError:
      raise
    except:
      sys.stderr.write('%s\n' % '\n'.join(
          traceback.format_exception_only(sys.exc_type, sys.exc_value)))
      LOGGER.debug(traceback.format_exc())
      return 1

  def RunCommand(self, pos_arg_values):
    """Runs the actual command after the flags are processed."""
    auth_retry = True

    while auth_retry:
      try:
        if self._IsListCommand():
          result, exceptions = self.RunListCommand(self._flags)
        else:
          result, exceptions = self.RunWithFlagsAndPositionalArgs(
              self._flags, pos_arg_values)
        auth_retry = False

        self.PrintResult(result)
        self.LogExceptions(exceptions)

        # If we just have an AccessTokenRefreshError raise it so
        # that we retry.
        for exception in exceptions:
          if isinstance(exception, oauth2_client.AccessTokenRefreshError):
            if not result:
              raise exception
            else:
              LOGGER.warning('Refresh error when running multiple '
                             'operations. Not automatically retrying as '
                             'some requests succeeded.')
              break

      except oauth2_client.AccessTokenRefreshError, e:
        if not auth_retry:
          raise
        # Retrying the operation will induce OAuth2 reauthentication and
        # creation of the new refresh token.
        LOGGER.info('OAuth2 token refresh error (%s), retrying.\n', str(e))
        auth_retry = False

      return bool(exceptions)

  def CreateHttp(self):
    """Construct an HTTP object to use with an API call.

    This is useful when doing multithreaded work as httplib2 Http
    objects aren't threadsafe.

    Returns:
      An object that implements the httplib2.Http interface
    """
    http = self._AuthenticateWrapper(httplib2.Http())
    return http

  def RunWithFlagsAndPositionalArgs(self, flag_values, pos_arg_values):
    """Run the command with the parsed flags and positional arguments.

    This method is what a subclass should override if they do not want
    to use the REST API.

    Args:
      flag_values: The parsed FlagValues instance.
      pos_arg_values: The positional arguments for the Handle method.

    Raises:
      CommandError: If user choses to not proceed with the command at safety
          prompt.

    Returns:
      A tuple (result, exceptions) where results is a
      JSON-serializable result and exceptions is a list of exceptions
      that were thrown when running this command.
    """
    http = self.CreateHttp()
    compute_api = self._BuildComputeApi(http)
    self._operations_api = compute_api.operations()
    self.SetApi(compute_api)

    if not self._HandleSafetyPrompt(pos_arg_values):
      raise CommandError('Operation aborted')

    exceptions = []
    result = self.Handle(*pos_arg_values)
    if isinstance(result, tuple):
      result, exceptions = result
    if self._flags.synchronous_mode:
      result = self.WaitForOperation(flag_values, time, result)
    if isinstance(result, list):
      result = self.MakeListResult(result, 'operationList')

    return result, exceptions

  def RunListCommand(self, flag_values):
    """Runs a command to list Google Compute Engine resources."""
    assert self._IsListCommand()

    if self._flags.sort_by:
      LOGGER.warn(
          'Sorting was requested. Sorting requires gcutil to fetch all '
          'resources in the collection, so this command may take longer than '
          'usual to complete.')

    http = self.CreateHttp()
    compute_api = self._BuildComputeApi(http)
    self._operations_api = compute_api.operations()
    self.SetApi(compute_api)

    all_exceptions = []
    collection = {'items': []}
    page_token = None

    fetch_all = flag_values.fetch_all_pages or flag_values.sort_by is not None

    while True:
      if fetch_all:
        page_size = None
      else:
        page_size = min(MAX_PAGE_SIZE,
                        flag_values.max_results - len(collection['items']))
      result = self.Handle(page_size, page_token)

      if isinstance(result, tuple):
        result, exceptions = result
        all_exceptions.append(exceptions)

      collection['items'] += result.get('items', [])

      if 'kind' in result and 'kind' not in collection:
        collection['kind'] = result['kind']

      page_token = result.get('nextPageToken')

      # Stops fetching resources if the last response has no
      # 'nextPageToken' key.
      if not page_token:
        break

      # Stops fetching resources if sorting was not requested and the
      # number of resources fetched has reached the maximum number
      # requested.
      if not fetch_all and len(collection['items']) >= flag_values.max_results:
        break

    return collection, all_exceptions

  def IsResultAnOperation(self, result):
    """Determine if the result object is an operation."""
    try:
      return ('kind' in result
              and result['kind'].endswith('#operation'))
    except TypeError:
      return False

  def IsResultAnOperationList(self, result):
    """Determine if the result object is an operation list."""
    try:
      return ('kind' in result
              and result['kind'].endswith('#operationList'))
    except TypeError:
      return False

  def IsResultAList(self, result):
    """Determine if the result object is a list of some sort."""
    try:
      return ('kind' in result
              and result['kind'].endswith('List'))
    except TypeError:
      return False

  def MakeListResult(self, results, kind_base):
    """Given an array of results, create an list object for those results.

    Args:
      results: The list of results.
      kind_base: The kind of list to create

    Returns:
      A synthetic list resource created from the list of individual results.
    """
    return {
        'kind': self._GetResourceApiKind(kind_base),
        'items': results,
        'note': ('This JSON result is based on multiple API calls. This '
                 'object was created in the client.')
        }

  def ExecuteRequests(self, requests):
    """Execute a list of requests in a thread pool.

    Args:
      requests: A list of requests objects to execute.

    Returns:
      A tuple with (results, exceptions) where result list is the list
      of all results and exceptions is any exceptions that were
      raised.
    """
    tp = thread_pool.ThreadPool(self._flags.concurrent_operations)
    ops = []
    for request in requests:
      op = ApiThreadPoolOperation(
          request, self, self._flags.synchronous_mode)
      ops.append(op)
      tp.Add(op)
    tp.WaitShutdown()
    results = []
    exceptions = []
    for op in ops:
      if op.RaisedException():
        exceptions.append(op.Result())
      else:
        if isinstance(op.Result(), list):
          results.extend(op.Result())
        else:
          results.append(op.Result())
    return (results, exceptions)

  def WaitForOperation(self, flag_values, timer, result, http=None):
    """Wait for a potentially asynchronous operation to complete.

    Args:
      flag_values: The parsed FlagValues instance.
      timer: An implementation of the time object, providing time and sleep
          methods.
      result: The result of the request, potentially containing an operation.
      http: An optional httplib2.Http object to use for requests.

    Returns:
      The synchronous return value, usually an operation object.
    """
    resource = None
    if not self.IsResultAnOperation(result):
      return result

    start_time = timer.time()
    operation_type = result['operationType']
    target = result['targetLink'].split('/')[-1]

    while result['status'] != 'DONE':
      if timer.time() - start_time >= flag_values.max_wait_time:
        LOGGER.warn('Timeout reached. %s of %s has not yet completed. '
                    'The operation (%s) is still %s.',
                    operation_type, target, result['name'], result['status'])
        break  # Timeout

      LOGGER.info('Waiting for %s of %s. Sleeping for %ss.',
                  operation_type, target, flag_values.sleep_between_polls)
      timer.sleep(flag_values.sleep_between_polls)

      # Poll the operation for status.
      request = self._operations_api.get(
          project=self._project,
          operation=result['name'])
      result = request.execute(http=http)
    else:
      if result['operationType'] != 'delete' and 'error' not in result:
        # We are going to replace the operation with its resulting resource.
        # Save the operation to return as well.
        target_link = result['targetLink']
        http = self.CreateHttp()
        response, data = http.request(target_link, method='GET')
        if 200 <= response.status <= 299:
          resource = json.loads(data)

    if resource is not None:
      results = []
      results.append(result)
      results.append(resource)
      return results
    return result

  def CommandGetHelp(self, unused_argv, cmd_names=None):
    """Get help for command.

    Args:
      unused_argv: Remaining command line flags and arguments after parsing
                   command (that is a copy of sys.argv at the time of the
                   function call with all parsed flags removed); unused in this
                   implementation.
      cmd_names:   By default, if help is being shown for more than one command,
                   and this command defines _all_commands_help, then
                   _all_commands_help will be displayed instead of the class
                   doc. cmd_names is used to determine the number of commands
                   being displayed and if only a single command is display then
                   the class doc is returned.

    Returns:
      __doc__ property for command function or a message stating there is no
      help.
    """
    help_str = super(
        GoogleComputeCommand, self).CommandGetHelp(unused_argv, cmd_names)
    return '%s\n\nUsage: %s' % (help_str, self._GetUsage())

  def _GetUsage(self):
    """Get the usage string for the command, used to print help messages.

    Returns:
      The usage string for the command.
    """
    res = '%s [--global_flags] %s [--command_flags]' % (
        os.path.basename(sys.argv[0]), self._command_name)

    args = getattr(self, 'positional_args', None)
    if args:
      res = '%s %s' % (res, args)

    return res

  def Handle(self):
    """Actual implementation of the command.

    Derived classes override this method, adding positional arguments
    to this method as required.

    Returns:
      Either a single JSON-serializable result or a tuple of a result
      and a list of exceptions that are thrown.
    """
    raise NotImplementedError()

  def SetFlags(self, flag_values):
    """Set the flags to be used by the command.

    Args:
      flag_values: The parsed flags values.
    """
    self._flags = flag_values
    self._project = self._flags.project

  def GetFlags(self):
    """Get the flags object used by the command."""
    return self._flags

  def SetApi(self, api):
    """Set the Google Compute Engine API for the command.

    Derived classes override this method, pulling the necessary
    domain specific API out of the global API.

    Args:
      api: The Google Compute Engine API used by this command.
    """
    raise NotImplementedError()

  def _PresentElement(self, field_value):
    """Format a json value for tabular display.

    Strips off the project qualifier if present and elides the value
    if it won't fit inside of a max column size of 64 characters.

    Args:
      field_value: The json field value to be formatted.

    Returns:
      The formatted json value.
    """
    if isinstance(field_value, basestring):
      field_value = self._StripBaseUrl(field_value).strip('/')

      if field_value.startswith('projects/' + self._project):
        field_value_parts = field_value.split('/')
        if len(field_value_parts) > 3:
          field_value = '/'.join(field_value_parts[3:])
        else:
          field_value = field_value_parts[-1]
      if (self._flags.long_values_display_format == 'elided' and
          len(field_value) > 64):
        return field_value[:31] + '..' + field_value[-31:]
    return field_value

  def _FlattenObjectToList(self, instance_json, name_map):
    """Convert a json instance to a dictionary for output.

    Args:
      instance_json: A JSON object represented as a python dict.
      name_map: A list of key, json-path object tuples where the
          json-path object is either a string or a list of strings.
          ('name', 'container.id') or
          ('name', ['container.id.new', 'container.id.old'])

    Returns:
      A list of extracted values selected by the associated JSON path.  In
      addition, names are simplified to their shortest path components.
    """

    def ExtractSubKeys(json_object, subkey):
      """Extract and flatten a (possibly-repeated) field in a json object.

      Args:
        json_object: A JSON object represented as a python dict.
        subkey: a list of path elements, e.g. ['container', 'id'].

      Returns:
        [element1, element2, ...] or [] if the subkey could not be found.
      """
      if not subkey:
        return [self._PresentElement(json_object)]
      if subkey[0] in json_object:
        element = json_object[subkey[0]]
        if isinstance(element, list):
          return sum([ExtractSubKeys(x, subkey[1:]) for x in element], [])
        return ExtractSubKeys(element, subkey[1:])
      return []

    ret = []
    for unused_key, paths in name_map:
      # There may be multiple possible paths indicating the field name due to
      # versioning changes.  Walk through them in order until one is found.
      if isinstance(paths, basestring):
        elements = ExtractSubKeys(instance_json, paths.split('.'))
      else:
        for path in paths:
          elements = ExtractSubKeys(instance_json, path.split('.'))
          if elements:
            break

      ret.append(','.join([str(x) for x in elements]))
    return ret

  def __AddErrorsForOperation(self, result, table):
    """Add any errors present in the operation result to the output table.

    Args:
      result: The json dictionary returned by the server.
      table: The pretty printing table to be customized.
    """
    if 'error' in result:
      table.AddRow(('', ''))
      table.AddRow(('errors', ''))
      for error in result['error']['errors']:
        table.AddRow(('', ''))
        table.AddRow(('  error', error['code']))
        table.AddRow(('  message', error['message']))

  def LogExceptions(self, exceptions):
    """Log a list of exceptions returned in multithreaded operation."""
    for exception in exceptions:
      if isinstance(exception, errors.HttpError):
        self.LogHttpError(exception)
      elif isinstance(exception, Exception):
        sys.stderr.write('%s\n' % '\n'.join(traceback.format_exception_only(
            type(exception).__name__, exception)))

  def LogHttpError(self, http_error):
    """Do specific logging when we hit an HttpError."""

    def AddMessage(messages, error):
      msg = error.get('message')
      if msg:
        messages.add(msg)

    message = http_error.resp.reason
    try:
      data = json.loads(http_error.content)
      messages = set()
      if isinstance(data, dict):
        error = data.get('error', {})
        AddMessage(messages, error)
        for error in error.get('errors', []):
          AddMessage(messages, error)
      message = '\n'.join(messages)
    except ValueError:
      pass

    sys.stderr.write('Error: %s\n' % message)
    # Log the full error response for debugging purposes.
    LOGGER.debug(http_error.resp)
    LOGGER.debug(http_error.content)

  def PrintResult(self, result):
    """Pretty-print the result of the command.

    If a class defines a list of ('title', 'json.field.path') values named
    'fields', this list will be used to print a table of results using
    prettytable.  If self.fields does not exist, result will be printed as
    pretty JSON.

    Note that if the result is either an Operations object or an
    OperationsList, it will be special cased and formatted
    appropriately.

    Args:
      result: A JSON-serializable object to print.
    """
    if self._flags.print_json or self._flags.format == 'json':
      # We could have used the pprint module, but it produces
      # noisy output due to all of our keys and values being
      # unicode strings rather than simply ascii.
      print json.dumps(result, sort_keys=True, indent=2)
      return

    if result:
      if self._flags.format == 'names':
        self._PrintNamesOnly(result)
      elif self.IsResultAList(result):
        self._PrintList(result)
      else:
        self._PrintDetail(result)

  def _PrintNamesOnly(self, result):
    """Prints only names of the resources returned by Google Compute Engine API.

    Args:
      result: A GCE List resource to print.
    """
    if self._IsListCommand():
      results = result.get('items', [])
    else:
      results = [result]

    for obj in results:
      name = obj.get('name')
      if name:
        print name

  def _CreateFormatter(self):
    if self._flags.format == 'sparse':
      return table_formatter.SparsePrettyFormatter()
    elif self._flags.format == 'csv':
      return table_formatter.CsvFormatter()
    else:
      return table_formatter.PrettyFormatter()

  def _PrintList(self, result):
    """Prints a result which is a Google Compute Engine List resource.

    For the result of list commands, prints the table of resources.

    For the result of batch operations, splits the result list into
    operations and other resources and possibly prints two tables. The
    operations typically represent errors (unless printing results of
    listoperations command) whereas the real resources typically
    represent successfully completed operations.

    Args:
      result: A GCE List resource to print.
    """
    items = result.get('items', [])

    if self._IsListCommand():
      self._CreateAndPrintTable(
          items, None,
          getattr(self, 'summary_fields', None),
          self._flags.sort_by or getattr(self, 'default_sort_field', None))
      return

    # Split results into operations and the rest of resources.
    res = []
    ops = []
    for obj in items:
      if self.IsResultAnOperation(obj):
        ops.append(obj)
      else:
        res.append(obj)

    if res and ops:
      res_header = '\nTable of resources:\n'
      ops_header = '\nTable of operations:\n'
    else:
      res_header = ops_header = None

    if res or not ops:
      self._CreateAndPrintTable(res, res_header,
                                getattr(self, 'summary_fields', None),
                                getattr(self, 'default_sort_field', None))

    if ops:
      self._CreateAndPrintTable(ops, ops_header,
                                self.operation_summary_fields,
                                self.operation_default_sort_field)

  def _CreateAndPrintTable(self, values, header, fields, sort_col):
    """Creates a table representation of the list of resources and prints it.

    Args:
      values: List of resources to display.
      header: A header to print before the table (can be None).
      fields: Summary field definition for the table.
      sort_col: Field to sort by. Illegal values of sort_col will lead to a
        DEBUG log message.
    """
    column_names = [x[0] for x in fields]
    rows = [self._FlattenObjectToList(row, fields) for row in values]

    if sort_col:
      reverse = False
      if sort_col.startswith('-'):
        reverse = True
        sort_col = sort_col[1:]

      if sort_col in column_names:
        sort_col_idx = column_names.index(sort_col)
        rows = sorted(rows, key=(lambda row: row[sort_col_idx]),
                      reverse=reverse)
      else:
        LOGGER.debug('Invalid sort column: ' + sort_col)

    if self._IsListCommand() and not self._flags.fetch_all_pages:
      # Truncates the list of results. If sorting was requested, all
      # the pages had to be fetched, so we have to truncate the final
      # results on the client side. If sorting was not requested, we
      # truncate anyway in case the server gives back more results
      # than requested.
      rows = rows[:self._flags.max_results]

    table = self._CreateFormatter()
    table.AddColumns(column_names)
    table.AddRows(rows)

    if header:
      print header
    print table

  def _PrintDetail(self, result):
    """Prints a detail view of the result which is an individual resource.

    Args:
      result: A resource to print.
    """
    if self.IsResultAnOperation(result):
      detail_fields = self.operation_detail_fields
    else:
      detail_fields = getattr(self, 'detail_fields', None)

    if not detail_fields:
      return

    row_names = [x[0] for x in detail_fields]
    table = self._CreateFormatter()
    table.AddColumns(('property', 'value'))
    property_bag = self._FlattenObjectToList(result, detail_fields)
    for i, v in enumerate(property_bag):
      table.AddRow((row_names[i], v))

    # Handle customized printing of this result.
    # Operations are special cased here.
    if self.IsResultAnOperation(result):
      self.__AddErrorsForOperation(result, table)
    elif hasattr(self, 'CustomizePrintResult'):
      self.CustomizePrintResult(result, table)

    print table

  def __GetRequiredAuthScopes(self):
    """Returns a list of scopes required for this command."""
    return scopes.DEFAULT_AUTH_SCOPES

  def SetFlagDefaults(self):
    if 'project' in FLAGS.FlagDict() and not FLAGS['project'].present:
      try:
        metadata = metadata_lib.Metadata()
        setattr(FLAGS, 'project', metadata.GetProjectId())
      except metadata_lib.MetadataError:
        pass

