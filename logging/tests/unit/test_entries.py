# Copyright 2016 Google Inc.
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

import unittest

import mock


class Test_logger_name_from_path(unittest.TestCase):

    def _call_fut(self, path):
        from google.cloud.logging.entries import logger_name_from_path

        return logger_name_from_path(path)

    def test_w_simple_name(self):
        LOGGER_NAME = 'LOGGER_NAME'
        PROJECT = 'my-project-1234'
        PATH = 'projects/%s/logs/%s' % (PROJECT, LOGGER_NAME)
        logger_name = self._call_fut(PATH)
        self.assertEqual(logger_name, LOGGER_NAME)

    def test_w_name_w_all_extras(self):
        LOGGER_NAME = 'LOGGER_NAME-part.one~part.two%part-three'
        PROJECT = 'my-project-1234'
        PATH = 'projects/%s/logs/%s' % (PROJECT, LOGGER_NAME)
        logger_name = self._call_fut(PATH)
        self.assertEqual(logger_name, LOGGER_NAME)


class Test_BaseEntry(unittest.TestCase):

    PROJECT = 'PROJECT'
    LOGGER_NAME = 'LOGGER_NAME'

    @staticmethod
    def _get_target_class():
        from google.cloud.logging.entries import _BaseEntry

        class _Dummy(_BaseEntry):
            _PAYLOAD_KEY = 'dummyPayload'

        return _Dummy

    def _make_one(self, *args, **kw):
        return self._get_target_class()(*args, **kw)

    def test_ctor_defaults(self):
        PAYLOAD = 'PAYLOAD'
        logger = _Logger(self.LOGGER_NAME, self.PROJECT)
        entry = self._make_one(PAYLOAD, logger)
        self.assertEqual(entry.payload, PAYLOAD)
        self.assertIs(entry.logger, logger)
        self.assertIsNone(entry.insert_id)
        self.assertIsNone(entry.timestamp)
        self.assertIsNone(entry.labels)
        self.assertIsNone(entry.severity)
        self.assertIsNone(entry.http_request)
        self.assertIsNone(entry.resource)

    def test_ctor_explicit(self):
        import datetime
        from google.cloud.logging.resource import Resource

        PAYLOAD = 'PAYLOAD'
        IID = 'IID'
        TIMESTAMP = datetime.datetime.now()
        LABELS = {'foo': 'bar', 'baz': 'qux'}
        SEVERITY = 'CRITICAL'
        METHOD = 'POST'
        URI = 'https://api.example.com/endpoint'
        STATUS = '500'
        REQUEST = {
            'requestMethod': METHOD,
            'requestUrl': URI,
            'status': STATUS,
        }
        resource = Resource(type='global', labels={})

        logger = _Logger(self.LOGGER_NAME, self.PROJECT)
        entry = self._make_one(PAYLOAD, logger,
                               insert_id=IID,
                               timestamp=TIMESTAMP,
                               labels=LABELS,
                               severity=SEVERITY,
                               http_request=REQUEST,
                               resource=resource)
        self.assertEqual(entry.payload, PAYLOAD)
        self.assertIs(entry.logger, logger)
        self.assertEqual(entry.insert_id, IID)
        self.assertEqual(entry.timestamp, TIMESTAMP)
        self.assertEqual(entry.labels, LABELS)
        self.assertEqual(entry.severity, SEVERITY)
        self.assertEqual(entry.http_request['requestMethod'], METHOD)
        self.assertEqual(entry.http_request['requestUrl'], URI)
        self.assertEqual(entry.http_request['status'], STATUS)
        self.assertEqual(entry.resource, resource)

    def test_from_api_repr_missing_data_no_loggers(self):
        client = _Client(self.PROJECT)
        PAYLOAD = 'PAYLOAD'
        LOG_NAME = 'projects/%s/logs/%s' % (self.PROJECT, self.LOGGER_NAME)
        API_REPR = {
            'dummyPayload': PAYLOAD,
            'logName': LOG_NAME,
        }
        klass = self._get_target_class()
        entry = klass.from_api_repr(API_REPR, client)
        self.assertEqual(entry.payload, PAYLOAD)
        self.assertIsNone(entry.insert_id)
        self.assertIsNone(entry.timestamp)
        self.assertIsNone(entry.severity)
        self.assertIsNone(entry.http_request)
        logger = entry.logger
        self.assertIsInstance(logger, _Logger)
        self.assertIs(logger.client, client)
        self.assertEqual(logger.name, self.LOGGER_NAME)

    def test_from_api_repr_w_loggers_no_logger_match(self):
        from datetime import datetime
        from google.cloud._helpers import UTC
        from google.cloud.logging.resource import Resource

        klass = self._get_target_class()
        client = _Client(self.PROJECT)
        PAYLOAD = 'PAYLOAD'
        SEVERITY = 'CRITICAL'
        IID = 'IID'
        NOW = datetime.utcnow().replace(tzinfo=UTC)
        TIMESTAMP = _datetime_to_rfc3339_w_nanos(NOW)
        LOG_NAME = 'projects/%s/logs/%s' % (self.PROJECT, self.LOGGER_NAME)
        LABELS = {'foo': 'bar', 'baz': 'qux'}
        METHOD = 'POST'
        URI = 'https://api.example.com/endpoint'
        RESOURCE = Resource(
            type='gae_app',
            labels={
                'type': 'gae_app',
                'labels': {
                    'module_id': 'default',
                    'version': 'test',
                }
            }
        )
        STATUS = '500'
        API_REPR = {
            'dummyPayload': PAYLOAD,
            'logName': LOG_NAME,
            'insertId': IID,
            'timestamp': TIMESTAMP,
            'labels': LABELS,
            'severity': SEVERITY,
            'httpRequest': {
                'requestMethod': METHOD,
                'requestUrl': URI,
                'status': STATUS,
            },
            'resource': RESOURCE._to_dict(),
        }
        loggers = {}
        entry = klass.from_api_repr(API_REPR, client, loggers=loggers)
        self.assertEqual(entry.payload, PAYLOAD)
        self.assertEqual(entry.insert_id, IID)
        self.assertEqual(entry.timestamp, NOW)
        self.assertEqual(entry.labels, LABELS)
        self.assertEqual(entry.severity, SEVERITY)
        self.assertEqual(entry.http_request['requestMethod'], METHOD)
        self.assertEqual(entry.http_request['requestUrl'], URI)
        self.assertEqual(entry.http_request['status'], STATUS)
        logger = entry.logger
        self.assertIsInstance(logger, _Logger)
        self.assertIs(logger.client, client)
        self.assertEqual(logger.name, self.LOGGER_NAME)
        self.assertEqual(loggers, {LOG_NAME: logger})
        self.assertEqual(entry.resource, RESOURCE)

    def test_from_api_repr_w_loggers_w_logger_match(self):
        from datetime import datetime
        from google.cloud._helpers import UTC

        client = _Client(self.PROJECT)
        PAYLOAD = 'PAYLOAD'
        IID = 'IID'
        NOW = datetime.utcnow().replace(tzinfo=UTC)
        TIMESTAMP = _datetime_to_rfc3339_w_nanos(NOW)
        LOG_NAME = 'projects/%s/logs/%s' % (self.PROJECT, self.LOGGER_NAME)
        LABELS = {'foo': 'bar', 'baz': 'qux'}
        API_REPR = {
            'dummyPayload': PAYLOAD,
            'logName': LOG_NAME,
            'insertId': IID,
            'timestamp': TIMESTAMP,
            'labels': LABELS,
        }
        LOGGER = object()
        loggers = {LOG_NAME: LOGGER}
        klass = self._get_target_class()
        entry = klass.from_api_repr(API_REPR, client, loggers=loggers)
        self.assertEqual(entry.payload, PAYLOAD)
        self.assertEqual(entry.insert_id, IID)
        self.assertEqual(entry.timestamp, NOW)
        self.assertEqual(entry.labels, LABELS)
        self.assertIs(entry.logger, LOGGER)


class TestProtobufEntry(unittest.TestCase):

    PROJECT = 'PROJECT'
    LOGGER_NAME = 'LOGGER_NAME'

    @staticmethod
    def _get_target_class():
        from google.cloud.logging.entries import ProtobufEntry

        return ProtobufEntry

    def _make_one(self, *args, **kw):
        return self._get_target_class()(*args, **kw)

    def test_constructor_basic(self):
        payload = {'foo': 'bar'}
        pb_entry = self._make_one(payload, mock.sentinel.logger)
        self.assertEqual(pb_entry.payload, payload)
        self.assertIsNone(pb_entry.payload_pb)
        self.assertIs(pb_entry.logger, mock.sentinel.logger)
        self.assertIsNone(pb_entry.insert_id)
        self.assertIsNone(pb_entry.timestamp)
        self.assertIsNone(pb_entry.labels)
        self.assertIsNone(pb_entry.severity)
        self.assertIsNone(pb_entry.http_request)

    def test_constructor_with_any(self):
        from google.protobuf.any_pb2 import Any

        payload = Any()
        pb_entry = self._make_one(payload, mock.sentinel.logger)
        self.assertIs(pb_entry.payload_pb, payload)
        self.assertIsNone(pb_entry.payload)
        self.assertIs(pb_entry.logger, mock.sentinel.logger)
        self.assertIsNone(pb_entry.insert_id)
        self.assertIsNone(pb_entry.timestamp)
        self.assertIsNone(pb_entry.labels)
        self.assertIsNone(pb_entry.severity)
        self.assertIsNone(pb_entry.http_request)

    def test_parse_message(self):
        import json
        from google.protobuf.json_format import MessageToJson
        from google.protobuf.struct_pb2 import Struct, Value

        LOGGER = object()
        message = Struct(fields={'foo': Value(bool_value=False)})
        with_true = Struct(fields={'foo': Value(bool_value=True)})
        PAYLOAD = json.loads(MessageToJson(with_true))
        entry = self._make_one(PAYLOAD, LOGGER)
        entry.parse_message(message)
        self.assertTrue(message.fields['foo'])


def _datetime_to_rfc3339_w_nanos(value):
    from google.cloud._helpers import _RFC3339_NO_FRACTION

    no_fraction = value.strftime(_RFC3339_NO_FRACTION)
    return '%s.%09dZ' % (no_fraction, value.microsecond * 1000)


class _Logger(object):

    def __init__(self, name, client):
        self.name = name
        self.client = client


class _Client(object):

    def __init__(self, project):
        self.project = project

    def logger(self, name):
        return _Logger(name, self)
