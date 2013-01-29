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

"""Commands for interacting with Google Compute Engine operations."""



from google.apputils import appcommands
import gflags as flags

from gcutil import command_base

FLAGS = flags.FLAGS


class OperationCommand(command_base.GoogleComputeCommand):
  """Base command for working with the operations collection.

  Attributes:
    default_sort_field: The json field name used to sort list output for the
        command.
    summary_fields: A set of tuples of (json field name, human
        readable name) used to generate a pretty-printed summary description
        of a list of operation resources.
    detail_fields: A set of tuples of (json field name, human
        readable name) used to generate a pretty-printed detailed description
        of an operation resource.
    resource_collection_name: The name of the REST API collection handled by
        this command type.
  """

  default_sort_field = (
      command_base.GoogleComputeCommand.operation_default_sort_field)
  summary_fields = command_base.GoogleComputeCommand.operation_summary_fields
  detail_fields = command_base.GoogleComputeCommand.operation_detail_fields

  resource_collection_name = 'operations'

  def SetApi(self, api):
    """Set the Google Compute Engine API for the command.

    Args:
      api: The Google Compute Engine API used by this command.
    """
    self._operations_api = api.operations()


class GetOperation(OperationCommand):
  """Retrieve an operation resource."""

  positional_args = '<operation-name>'

  def Handle(self, operation_name):
    """Get the specified operation.

    Args:
      operation_name: The name of the operation to get.

    Returns:
      The json formatted object resulting from retrieving the operation
      resource.
    """
    # Force asynchronous mode so the caller doesn't wait for this operation
    # to complete before returning.
    self._flags.synchronous_mode = False

    operation_request = self._operations_api.get(
        project=self._project,
        operation=self._DenormalizeResourceName(operation_name))

    return operation_request.execute()


class DeleteOperation(OperationCommand):
  """Delete one or more operations."""

  positional_args = '<operation-name-1> ... <operation-name-n>'
  safety_prompt = 'Delete operation'

  def Handle(self, *operation_names):
    """Delete the specified operations.

    Args:
      *operation_names: The names of the operations to delete.

    Returns:
      Tuple (results, exceptions) - results of deleting the operations.
    """
    requests = []
    for name in operation_names:
      requests.append(self._operations_api.delete(
          project=self._project,
          operation=self._DenormalizeResourceName(name)))
    _, exceptions = self.ExecuteRequests(requests)
    return '', exceptions


class ListOperations(OperationCommand):
  """List the operations for a project."""

  def Handle(self, page_size=None, page_token=None):
    """List the project's operations.

    Args:
      page_size: The size of the page to fetch.
      page_token: The next page token, as returned from the server.

    Returns:
      The json formatted object resulting from listing the operation resources.
    """
    operation_request = self._operations_api.list(
        **self._BuildListArgs(page_size, page_token))
    return operation_request.execute()


def AddCommands():
  appcommands.AddCmd('getoperation', GetOperation)
  appcommands.AddCmd('deleteoperation', DeleteOperation)
  appcommands.AddCmd('listoperations', ListOperations)
