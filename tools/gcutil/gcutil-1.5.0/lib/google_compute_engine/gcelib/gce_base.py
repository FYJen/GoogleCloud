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

"""The base class definition for the generated GoogleComputeEngine class."""

import collections
import cStringIO
from email.feedparser import FeedParser
from email.mime.multipart import MIMEMultipart
from email.mime.nonmultipart import MIMENonMultipart
import itertools
import json
import logging
import re
import time
import urllib
import urlparse

import httplib2

from gcelib import gce
from gcelib import shortcuts

LOG_FORMAT = '{start_bold}%(asctime)s{reset_colors} - %(message)s'.format(
    start_bold='\033[1m', reset_colors='\033[0m')

BASE_URL_VALIDATORS = [
    re.compile('https://www\.googleapis\.com/compute/[a-z0-9_]+/projects/?')
]

RESPONSE_ID_REGEX = re.compile('<response-([^>]*)>')

DEFAULT_BASE_URL = 'https://www.googleapis.com/compute/v1beta13/projects/'

# The maximum amount of time that should be spent polling an Operation
# object before giving up.
TIMEOUT_SECS = 60
BATCH_TIMEOUT_SECS = 300

# The maximum number of individual requests comprising one batch. Bigger batches
# will be split up into smaller payloads to send up to the server.
MAX_BATCH_SIZE = 1000


class GoogleComputeEngineBase(object):
  """The base class from which the generated code derives."""

  _SELF_LINK_REGEX = re.compile(
      'https?://[^/]+/compute/[^/]+/projects/([^/]+)(?:/.*)?')

  API_REQUEST = collections.namedtuple(
      'ApiRequest', ('method', 'url', 'query', 'body'))

  BATCH_RESPONSE = collections.namedtuple('BatchResponse', ('response', 'body'))

  def __init__(self, credentials,
               logging_level=logging.WARN,
               base_url=None,
               default_image=None,
               default_machine_type=None,
               default_network='default',
               default_network_interface=None,
               default_project=None,
               default_zone=None,
               trace_token=None):
    """Base class constructor.

    Args:
      credentials: A OAuth2Credentials object that contains the
        client's credentials.
      logging_level: The verbosity of the log messages as defined
        in the logging module.
      base_url: The base URL to which REST requests can be made. This
        should not be changed.
      default_image: The name of the default image. This value can be
        overwritten by the different API calls.
      default_machine_type: The name of the default machine type. This
        value can be overwritten by the different API calls.
      default_network: The default network. This value can be overwritten
        by the different API calls.
      default_network_interface: The default network interface. This
        value can be overwritten by the different API calls.
      default_project: The name of the default project. This value can
        be overwritten by the different API calls.
      default_zone: The name of the default zone. This value can be
        overwritten by the different API calls.
      trace_token: A Google-provided token that can be used to trace API
        calls. Note that specifying this token will cause all calls to be
        rate limited to one request every 10 seconds, with a maximum burst
        of 60 requests.

    Raises:
      ValueError: When an invalid base_url is provided.
    """
    self.credentials = credentials
    if base_url is None and hasattr(self, 'BASE_URL'):
      base_url = self.BASE_URL
    if base_url is None:
      base_url = DEFAULT_BASE_URL

    GoogleComputeEngineBase._check_url(base_url)

    self.base_url = base_url.rstrip('/')
    self.logger = logging.getLogger('GoogleComputeEngine')
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    self.logger.addHandler(handler)
    self.logger.setLevel(logging_level)

    self.default_image = default_image
    self.default_machine_type = default_machine_type
    self.default_network = default_network
    self.default_network_interface = (default_network_interface or
                                      shortcuts.network(default_network))
    self.default_project = default_project
    self.default_zone = default_zone

    self.trace_token = trace_token

  @property
  def default_image(self):
    return self._default_image

  @property
  def default_machine_type(self):
    return self._default_machine_type

  @property
  def default_network(self):
    return self._default_network

  @property
  def default_network_interface(self):
    return self._default_network_interface

  @property
  def default_project(self):
    return self._default_project

  @property
  def default_zone(self):
    return self._default_zone

  @default_image.setter
  def default_image(self, value):
    self._default_image = value

  @default_machine_type.setter
  def default_machine_type(self, value):
    self._default_machine_type = value

  @default_network.setter
  def default_network(self, value):
    self._default_network = value

  @default_network_interface.setter
  def default_network_interface(self, value):
    self._default_network_interface = value

  @default_project.setter
  def default_project(self, value):
    self._default_project = value

  @default_zone.setter
  def default_zone(self, value):
    self._default_zone = value

  @default_image.deleter
  def default_image(self):
    self._default_image = None

  @default_machine_type.deleter
  def default_machine_type(self):
    self._default_machine_type = None

  @default_network.deleter
  def default_network(self):
    self._default_network = 'default'

  @default_network_interface.deleter
  def default_network_interface(self):
    self._default_network_interface = shortcuts.network()

  @default_project.deleter
  def default_project(self):
    self._default_project = None

  @default_zone.deleter
  def default_zone(self):
    self._default_zone = None

  @property
  def trace_token(self):
    return self._trace_token

  @trace_token.setter
  def trace_token(self, value):
    self._trace_token = value

  @trace_token.deleter
  def trace_token(self):
    self._trace_token = None

  def _normalize(self, project, kind, resource):
    """Normalizes the URI for the given resource.

    A normalized resource URI contains the base URI, project
    identifier, and the resource identifier.

    Args:
      project: The name of the project.
      kind: The type of the resource (e.g., disks, images).
      resource: The name of the resource or the resource's URI.

    Returns:
      The URI to the given resource.
    """
    if resource.startswith(self.base_url):
      return resource

    if resource.startswith('projects/'):
      return '/'.join((self.base_url, resource[9:]))

    if resource.startswith('/projects/'):
      return '/'.join((self.base_url, resource[10:]))

    if resource.startswith(kind + '/'):
      return '/'.join((self.base_url, project, resource))

    return '/'.join((self.base_url, project, kind, resource))

  def _create_url_query(self, query_params):
    """Creates a url query params component from the given dict.

    If a tracing token was specified when constructing this object, it
    is included in the 'trace' key.

    Args:
      query_params: A dict containing the parameters and their values.

    Returns:
      A string representing the query params component of the URL (e.g.,
        'a=b&c=d').
    """
    query_params = {} if query_params is None else query_params
    if self.trace_token:
      query_params['trace'] = 'token:' + self.trace_token

    return '&'.join('{0}={1}'.format(key, urllib.quote_plus(str(value)))
                    for key, value in sorted(query_params.iteritems()))

  def _sleep(self, seconds):
    """Sleeps for specified number of seconds. Can be overriden by tests."""
    time.sleep(seconds)

  def _send_request(self, path, method='GET', request_body=None,
                    content_type='application/json'):
    """Send a API request to the server."""
    headers = {}
    if request_body:
      headers['content-type'] = content_type
    elif method == 'POST':
      headers['content-length'] = '0'

    self.logger.info('Sending {0} request to {1}.'.format(method, path))
    if request_body:
      self.logger.debug('Request body: {0}'.format(request_body))

    http = self.credentials.authorize(httplib2.Http())
    response, body = http.request(
        path, method=method, body=request_body, headers=headers)

    self.logger.debug('Received response: {0}'.format(response))
    if body:
      self.logger.debug('Response body: {0}'.format(body))

    return response, body

  def _send_request_json(self, path, method='GET', body=None):
    """Sends a request to the server and interprets response body as JSON.

    This method does lots of error checking.

    Args:
      path: The request path.
      method: The HTTP method to use.
      body: The request body, if any.

    Raises:
      GceError: If there is a problem with the response (e.g., status code
        not in range [200, 299], unparsable response, ..._).

    Returns:
      The response body parsed as JSON or None if the response body is empty.
    """
    response, body = self._send_request(path, method, body)
    if 200 <= response.status <= 299:
      # The server returns an empty body when deleting operation resources.
      if not body:
        return None

      try:
        return json.loads(body)
      except ValueError:
        raise gce.GceError(message='Server returned error: {0}'.format(body))

    # The status code was not in the range [200, 299].

    if not body:
      raise gce.GceError(status=response.status)

    # Attempts to treat the response as JSON and parses it.
    try:
      resource = json.loads(body)
    except ValueError:
      raise gce.GceError(message='Server returned error: {0}'.format(body),
                         status=response.status)

    status = self._get_status(resource, response.status)

    # Checks to see if the response contains an error.
    error = self._get_error_from_resource(resource)
    if error:
      raise gce.GceError(message=error, status=status)

    # At this point, we're out of options. :(
    raise gce.GceError(status=status)

  def _get_error_from_resource(self, resource):
    """Returns the first error message in the resource or None."""
    # Currently, if there is an error, the server sends back exactly
    # one error message. This is not an API contract, but it's the
    # truth for the time being.
    if ('error' in resource and
        'errors' in resource['error'] and
        resource['error']['errors']):
      return resource['error']['errors'][0].get('message')
    else:
      return None

  def _get_status(self, resource, status=None):
    """Returns resource['httpErrorStatusCode'] or status."""
    return resource.get('httpErrorStatusCode', status)

  def _execute(self, request, blocking=True):
    """Calls the Google Compute Engine backend with the given parameters.

    Args:
      request: An instance of API_REQUEST named tuple describing the request.
      blocking: Wait for an asynchronous opration to complete before returning.

    Raises:
      GceError: If there are any issues with the request.

    Returns:
      A Google Compute Engine object that is returned by the server or None if
        the response body is empty.
    """
    base = urlparse.urlsplit(self.base_url)
    path = urlparse.urlunsplit(
        (base.scheme, base.netloc,
         '{0}/{1}'.format(base.path.rstrip('/'), request.url),
         self._create_url_query(request.query), ''))
    GoogleComputeEngineBase._check_url(path)

    result = self._send_request_json(path, request.method, request.body)
    if result is None:
      return None

    if blocking:
      result = self._wait_for(operation=result)
    return self._parse(result)

  def _wait_for(self, operation, timeout_secs=TIMEOUT_SECS):
    """Blocks until the given operation's status is DONE.

    Args:
      operation: The operation to poll. This should be a dict
        corresponding to an Operation resource.
      timeout_secs: The maximum amount of time this method will
        wait for completion of an operation.

    Raises:
      ValueError: If the timeout expires or the given resource is
        not an Operation.

    Returns:
      For non-delete operations, a tuple where the first element is a
      dict corresponding to the Operation and the second element is
      the object that was mutated. Deletes return just the operation.
    """
    if operation.get('kind') != 'compute#operation':
      raise gce.GceError(
          message=('Only objects of type Operation can be polled. Received: ' +
                   str(operation)))

    self_link = operation.get('selfLink')
    if not self_link:
      raise gce.GceError(
          message=('Operation resource is missing selfLink. Received: ' +
                   str(operation)))

    timeout = _TimeoutChecker(timeout_secs)
    delay = 0.0
    while True:
      self.logger.debug('Polling operation {0}...'.format(operation.get('id')))
      operation = self._send_request_json(self_link)

      if timeout.check_timeout():
        raise ValueError('Polling timed out.')

      if operation.get('status') == 'DONE':
        break

      delay = min(max(delay * 1.5, 1.0), 5.0)
      self.logger.debug('Operation has not completed. Polling again in {0} '
                        'seconds.'.format(delay))
      self._sleep(delay)

    self.logger.info('Operation is done.')

    if 'error' in operation:
      raise gce.GceError(message=self._get_error_from_resource(operation),
                         status=self._get_status(operation))

    if operation.get('operationType') == 'delete':
      return operation

    target_link = operation.get('targetLink')
    return self._send_request_json(target_link)

  def _wait_for_list(self, operations, timeout_secs=BATCH_TIMEOUT_SECS):
    """Waits for completion of batch of asynchronous operations.

    Keeps track of incomplete operations. Requests operation status in batches.
    As operations transition to "DONE" state it will resolve the operation
    target resource and include that in the response.

    In case of errors, inserts an error object into the result.

    Args:
      operations: list of operations to await completion.
      timeout_secs: timeout in seconds. Infinite if value <= 0.

    Returns:
      List of resolved resources that the operations created/modified, or None
      if objects were deleted.
    """
    # Results are constructed as list of tuples (index, value) where index is
    # the index in the original list of operations. At the end they are sorted
    # and the indices are thrown away.
    results = []

    operations = list(operations)
    op_indices = range(len(operations))  # Parallel list with indices for sort.

    delay = 0.0
    timeout = _TimeoutChecker(timeout_secs)

    while operations:
      requests = []
      request_indices = []

      timeout_occurred = timeout.check_timeout()

      for index, operation in itertools.izip(op_indices, operations):
        kind = operation.get('kind')
        if kind is None:
          results.append((index, gce.GceError(
              message='Server returned invalid resource: ' + str(operation),
              status=400)))
          continue

        if kind != 'compute#operation':
          # We just resolved the resource, append it to the result.
          results.append((index, operation))
          continue

        if operation.get('status') != 'DONE':
          # Still waiting for the operation.
          request_url = operation.get('selfLink')
          if not request_url:
            results.append((index, gce.GceError(
                message=('Operation resource is missing selfLink property: ' +
                         str(operation)),
                status=400)))
            continue
        else:
          # Operation is done, check for error status and schedule fetching of
          # the completed resource.
          if 'error' in operation:
            results.append((index, gce.GceError(
                message=self._get_error_from_resource(operation),
                status=self._get_status(operation, 400))))
            continue

          request_url = operation.get('targetLink')
          if operation.get('operationType') == 'delete' or not request_url:
            results.append((index, None))
            continue

        if timeout_occurred:
          results.append((index, gce.GceError(
              message='Asynchronous operation timeout.',
              status=400)))
        else:
          requests.append(GoogleComputeEngineBase.API_REQUEST(
              'GET', request_url, None, None))
          request_indices.append(index)

      if not requests:
        break  # No more requests to send up to the server.

      # Delay before sending the request.
      delay = min(max(delay * 1.5, 1.0), 5.0)
      self._sleep(delay)

      # Send the requests to the server as a batch.
      responses = self._execute_batch_request(requests)

      # Process the responses.
      resources = []
      resource_indices = []
      for index, response in itertools.izip(request_indices, responses):
        if response.response.status >= 300:
          results.append((index, gce.GceError(
              message=response.response.reason,
              status=response.response.status)))
          continue

        if not response.body:
          results.append((index, gce.GceError(
              message='Server returned an empty resource as a response.',
              status=400)))
          continue

        try:
          resource = json.loads(response.body)
        except ValueError:
          results.append((index, gce.GceError(
              message='Server returned invalid JSON response: ' + response.body,
              status=400)))
          continue

        resources.append(resource)
        resource_indices.append(index)

      operations = resources
      op_indices = resource_indices

    results.sort(key=lambda r: r[0])
    return [r[1] for r in results]

  def _parse_list(self, resources):
    """Parses a list of resources returned from the server."""
    results = []
    for r in resources:
      try:
        result = self._parse(r)
      except gce.GceError as e:
        result = e
      results.append(result)
    return results

  def _generate(self, method, uri, query_params):
    """Generates all resources described by the given parameters.

    This method makes the list methods easier to use by taking care of
    paging under the covers (since each list method can return at most
    100 resources).

    Args:
      method: The method to use to fetch the resources.
      uri: The location of the resources.
      query_params: Query parameters that can be used to filter the
        results.

    Yields:
      One resource at a time.
    """
    query_params = dict(query_params)
    request = GoogleComputeEngineBase.API_REQUEST(
        method, uri, query_params, None)
    while True:
      result = self._execute(request, blocking=False)
      items = result.items
      next_page_token = result.nextPageToken
      if not items:
        break
      for item in items:
        yield item
      if not next_page_token:
        break
      query_params['pageToken'] = next_page_token

  def _get_parsers(self):
    """Returns a dict that maps resource types to parsing functions.

    The resource types should be strings that identify a resource
    (e.g., 'compute#instance') and the parsing functions should
    construct an object defined in the generated code from a resource
    dict.
    """
    raise NotImplementedError('_get_parsers() must be implemented by subclass.')

  def _parse(self, val):
    """Parses the given val (a dict) into a resource object.

    Args:
      val: A dict representing a resource. The dict must contain a
        'kind' key that specifies the type of the resource (e.g.,
        'compute#instance').

    Raises:
      GceError: If the given val cannot be parsed.

    Returns:
      A Google Compute Engine object corresponding to val.
    """
    if val is None:
      return None
    if isinstance(val, BaseException):
      return val

    kind = val.get('kind')
    if not kind:
      raise gce.GceError(
          message='No kind attribute found in input: ' + str(val))

    func = self._get_parsers().get(kind)
    if func is None:
      raise gce.GceError(
          message='Could not recognize response from server: ' + str(val))
    return func(val, self)

  @staticmethod
  def _parse_project(self_link):
    """Extracts project name from the absolute URL of selfLink property."""
    if self_link is not None:
      match = GoogleComputeEngineBase._SELF_LINK_REGEX.match(self_link)
      if match:
        return match.group(1)
    return None

  @staticmethod
  def _combine(list1, list2):
    """Combines two sequences much like izip, allowing either to be None."""
    if list1 is not None:
      if list2 is not None:
        # This won't work for inputs being generators. Consider allowing them.
        if len(list1) != len(list2):
          raise ValueError('List of objects and names must be equal length')
        return itertools.izip(list1, list2)
      else:
        return itertools.izip(list1, itertools.repeat(None))
    elif list2 is not None:
      return itertools.izip(itertools.repeat(None), list2)
    else:
      return []

  def _serialize_batch_api_request(self, base_path, request):
    """Serializes one API request into an individual MIME part.

    The MIME part becomes part of the larger multipart MIME message. Each
    individual part contains a single API request in the format:

    VERB url
    [Content-Type: application/json
    Content-Length: <length>

    JSON payload]

    The section enclosed in [] is only present for requests with JSON payload.

    Args:
      base_path: The API service base path.
      request: An instance of GoogleComputeEngineBase.API_REQUEST named tuple.

    Returns:
      string containing serialized HTTP request to be assembled into MIME
      multipart HTTP request.
    """
    request_url_split = urlparse.urlsplit(request.url)
    if request_url_split.netloc:
      url_path = request_url_split.path
    else:
      url_path = '{0}/{1}'.format(base_path, request.url)
    url = urlparse.urlunsplit((
        None, None, url_path, self._create_url_query(request.query), ''))

    result = '{0} {1}\n'.format(request.method, url.encode('utf-8'))
    if request.body:
      body = cStringIO.StringIO()
      body.write(result)
      body.write('Content-Type: application/json\n')
      body.write('Content-Length: {0}\n\n'.format(len(request.body)))
      body.write(request.body)
      result = body.getvalue()
    return result

  def _parse_batch_api_response(self, response):
    """Parses an individual part of the MIME multipart server response.

    Args:
      response: One part of the MIME mutlipart message, string.
    Raises:
      ValueError: if an invalid HTTP header is encountered.
    Returns:
      An instance of GoogleComputeEngineBase.BATCH_RESPONSE named tuple.
    """
    status, payload = response.split('\n', 1)
    split = status.split(None, 2)
    if len(split) > 1:
      status = split[1]
      reason = split[2] if len(split) > 2 else ''
    else:
      raise ValueError('Invalid HTTP server response.')

    parser = FeedParser()
    parser.feed(payload)
    msg = parser.close()
    msg['status'] = status
    http_response = httplib2.Response(msg)
    http_response.reason = reason
    payload = msg.get_payload()
    return GoogleComputeEngineBase.BATCH_RESPONSE(http_response, payload)

  def _send_batch_request(self, requests):
    """Sends a batch of requests to the server and processes the HTTP responses.

    Args:
      requests: List of GoogleComputeEngineBase.API_REQUEST named tuples. Must
        contain <= MAX_BATCH_SIZE elements.

    Raises:
      ValueError: If requests has more than MAX_BATCH_SIZE elements.

    Returns:
      List of GoogleComputeEngineBase.BATCH_RESPONSE named tuples, one for
      each element of request parameter.
    """
    if len(requests) > MAX_BATCH_SIZE:
      raise ValueError('Too many requests provided'
                       '(maximum is {0})'.format(MAX_BATCH_SIZE))

    batch = _BatchApiRequest()
    base = urlparse.urlsplit(self.base_url)
    base_path = base.path.rstrip('/')
    for i, request in enumerate(requests):
      msg = MIMENonMultipart('application', 'http')
      msg.add_header('Content-ID', '<{0}>'.format(i))
      msg.set_payload(self._serialize_batch_api_request(base_path, request))
      batch.attach(msg)

    batch_string = batch.as_string()
    content_type = 'multipart/mixed; boundary="{0}"'.format(
        batch.get_boundary())

    url = urlparse.urlunsplit((base.scheme, base.netloc, 'batch',
                               self._create_url_query(None), None))
    response, data = self._send_request(url, 'POST', batch_string, content_type)

    if response.status >= 300:
      error = gce.GceError(
          message=response.reason, status=response.status)
      return [error] * len(requests)  # Return all errors.
    elif not data:
      error = gce.GceError(
          message='Server returned no data', status=response.status)
      return [error] * len(requests)  # Return all errors.

    # Process successful response.
    data = 'content-type: {0}\r\n\r\n'.format(response['content-type']) + data
    parser = FeedParser()
    parser.feed(data)
    response = parser.close()

    responses = []
    for part in response.get_payload():
      responses.append((
          int(RESPONSE_ID_REGEX.match(part['Content-ID']).group(1)),
          self._parse_batch_api_response(part.get_payload())))

    responses.sort(key=lambda r: r[0])
    return [r[1] for r in responses]

  def _execute_batch_request(self, requests, batch_size=MAX_BATCH_SIZE):
    """Executes a batch request.

    The server imposes a limit on how many requests can be in the batch.
    This function will split up requests into smaller batches if needed.
    If any request from the batch fails with expired access token, credentials
    will be refreshed and the failed request will be retried.

    Args:
      requests: iterable of GoogleComputeEngineBase.API_REQUEST objects.
      batch_size: size of the individual batch to send to the server.

    Returns:
      List of responses from the server - instances of
      GoogleComputeEngineBase.BATCH_RESPONSE named tuples.
    """
    batch_size = min(batch_size, MAX_BATCH_SIZE)
    requests = list(requests)
    responses = []

    while requests:
      # Take only the first MAX_BATCH_SIZE requests.
      batch_request = requests[:batch_size]
      requests = requests[batch_size:]

      batch_response = self._send_batch_request(batch_request)

      redo_indices = [i for i, r in enumerate(batch_response)
                      if r.response.status == 401]
      if redo_indices:
        redo_requests = [batch_request[i] for i in redo_indices]
        self.credentials.refresh(httplib2.Http())
        redo_responses = self._send_batch_request(redo_requests)
        for i, r in enumerate(redo_responses):
          batch_response[redo_indices[i]] = r

      responses.extend(batch_response)

    return responses

  def _execute_list(self, requests, blocking=True, parse=True):
    """Executes list of API requests.

    Args:
      requests: Iterable of request, each is an instance of API_REQUEST named
        tuple defined above.
      blocking: Wait for asynchronous operations to complete before returning.
      parse: If True ,parse the resulting JSON into an object representation.

    Returns:
      List of response objects (unparsed).
    """
    responses = self._execute_batch_request(requests)
    # Extract successful responses, process errors
    success_indices = []
    for i, r in enumerate(responses):
      if r.body:
        try:
          response_json = json.loads(r.body)
        except ValueError:
          response_json = None

      if 200 <= r.response.status <= 299:
        success_indices.append(i)
        responses[i] = response_json
      else:
        responses[i] = gce.GceError(
            message=self._get_error_from_resource(response_json),
            status=self._get_status(response_json, r.response.status))

    if success_indices:
      successes = [responses[i] for i in success_indices]
      if blocking:
        successes = self._wait_for_list(successes)
      if parse:
        successes = self._parse_list(successes)

      for i, s in enumerate(successes):
        responses[success_indices[i]] = s

    return responses

  @staticmethod
  def _check_url(url):
    """Ensures that the given URL conforms to the expected API URL.

    Args:
      url: The URL to check.

    Raises:
      ValueError: If the base URL is malformed.
    """
    for validator in BASE_URL_VALIDATORS:
      if validator.match(url):
        return

    raise ValueError(
        'Invalid base URL. '
        'The URL {0} must match one of the following patterns: ({1})'.format(
            repr(url),
            ', '.join([repr(v.pattern) for v in BASE_URL_VALIDATORS])))

  @staticmethod
  def _strings_to_json(value):
    """Serializes iterable of strings to list. Promotes string to list.

    Args:
      value: the value to convert to list of strings. It can be a iterable of
      strings or an individual string, in which case it is promoted to list.
    Returns:
      List of strings.
    Raises:
      ValueError: If the value is None.
    """
    if value is None:
      raise ValueError('strings cannot be None.')
    elif isinstance(value, basestring):
      return [value]
    else:
      return list(value)

  @staticmethod
  def _json_to_strings(value):
    """Deserializes list of strings from json.

    Used by the generated code to parse the list of string values. Basically
    only creates copy of the list but tolerates None.

    Input: ['value1', 'value2', ... 'valueN'], or None

    Args:
      value: The list deserialized from json.
    Returns:
      List of strings extracted from the json list.
    """
    return None if value is None else list(value)


class ListObjectBase(object):
  """Common base class for all classes representing lists of objects."""
  __slots__ = ['__items']

  def __init__(self, items):
    self.__items = items

  def __iter__(self):
    if self.__items is not None:
      for i in self.__items:
        yield i

  def __len__(self):
    return len(self.__items) if self.__items is not None else 0

  def __getitem__(self, index):
    return self.items.__getitem__(index)


class _BatchApiRequest(MIMEMultipart):
  """Represents a batch API request, overrides header writing behavior."""

  def _write_headers(self, msg):
    # We write the headers for the multipart message manually so to that end we
    # override _write_headers to signal the email library that we implement our
    # own header logic.
    pass


class _TimeoutChecker(object):
  """Tracks a time at which the operation will have timed out."""
  __slots__ = ('_timeout')

  def __init__(self, timeout_secs):
    """Initializes TimeoutChecker with number of seconds until the timeout.

    The function will calculate the absolute point in the future at which point
    the timeout occurs.

    Args:
      timeout_secs: Number of seconds until timeout.
    """
    self._timeout = (time.time() + timeout_secs) if timeout_secs >= 0 else -1

  def check_timeout(self):
    """Returns True if timeout occurred."""
    return self._timeout > 0 and time.time() > self._timeout
