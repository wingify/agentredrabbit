try:
    import unittest2 as unittest
except ImportError:
    import unittest

from mock import Mock
import threading
import pika
from agentredrabbit import config
from agentredrabbit import transport

published_message = "random published message"


def mock_publish(exchange, key, msg, properties, mandatory):
    global published_message
    published_message = msg


def mock_publish_exception(exchange, key, msg, properties, mandatory):
    raise pika.exceptions.ChannelClosed


class TransportTests(unittest.TestCase):
    def test_transport_redis(self):
        global published_message
        transporter = transport.Transporter("1", threading.Lock(),
                                            config.ReadConfig(),
                                            "queue1", threading.Event())

        transporter.stopping = False
        test_message = "{'key1': 'value1', 'key2': 'value2'}"
        transporter.redis = Mock()
        transporter.redis.chunk_pop.return_value = ([test_message]*10, False)
        transporter.channel = Mock()

        transporter.channel.basic_publish = mock_publish
        transporter.schedule_next_message = Mock(return_value=None)
        return_value = transporter.publish_message()
        self.assertEqual(return_value, None)
        self.assertEqual(published_message, "\n".join([test_message] * 10))

    def test_transport_failsafeq(self):
        global published_message
        transporter = transport.Transporter("1", threading.Lock(),
                                            config.ReadConfig(),
                                            "queue1", threading.Event())

        transporter.stopping = False
        test_message = "{'key1': 'value1', 'key2': 'value2'}"
        failsafeq = {"queue1": [[test_message]]}
        transport.setFailsafeQueue(failsafeq)
        transporter.channel = Mock()
        transporter.channel.basic_publish = mock_publish
        transporter.schedule_next_message = Mock(return_value=None)
        return_value = transporter.publish_message()
        self.assertEqual(return_value, None)
        self.assertEqual(published_message, test_message)

    def test_transport_pika_exception(self):
        global published_message
        transporter = transport.Transporter("1", threading.Lock(),
                                            config.ReadConfig(),
                                            "queue1", threading.Event())

        transporter.stopping = False
        test_message = "{'key1': 'value1', 'key2': 'value2'}"
        transporter.redis = Mock()
        transporter.redis.chunk_pop.return_value = ([test_message]*10, False)
        transporter.channel = Mock()

        transporter.channel.basic_publish = mock_publish_exception
        transporter.schedule_next_message = Mock(return_value=None)
        return_value = transporter.publish_message()
        self.assertEqual(return_value, None)
        self.assertEqual(transport.getFailsafeQueue()["queue1"][0],
                         [test_message] * 10)

    def test_transport_stopping(self):
        transporter = transport.Transporter("1", threading.Lock(),
                                            config.ReadConfig(),
                                            "queue1", threading.Event())
        transporter.stopping = True
        return_value = transporter.publish_message()
        self.assertEqual(return_value, None)
