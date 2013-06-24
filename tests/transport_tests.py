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
    def setUp(self):
        unittest.TestCase.setUp(self)
        self.transporter = transport.Transporter("1", threading.Lock(),
                                                 config.ReadConfig(),
                                                 "queue1", threading.Event())
        self.transporter.stopping = False
        self.test_message = "{'key1': 'value1', 'key2': 'value2'}"

        self.transporter.redis = Mock()
        self.transporter.redis.chunk_pop.return_value = ([self.test_message]*8,
                                                         False)
        self.transporter.channel = Mock()
        self.transporter.channel.basic_publish = mock_publish
        self.transporter.schedule_next_message = Mock(return_value=None)

    def test_delivery_confirmation_ack(self):
        frame = Mock()
        frame.method.NAME = "something.ACK.somethingelse"
        frame.method.delivery_tag = 1234
        self.assertFalse(1234 in self.transporter.deliveries)
        self.transporter.deliveries.append(1234)
        self.assertTrue(1234 in self.transporter.deliveries)
        self.transporter.on_delivery_confirmation(frame)
        self.assertFalse(1234 in self.transporter.deliveries)

    def test_shutdown_event_check(self):
        self.transporter.stop = Mock()
        self.transporter.shutdown_event.set()
        self.transporter.publishing = True
        self.assertFalse(self.transporter.shutdown_event_check())
        self.transporter.publishing = False
        self.assertTrue(self.transporter.shutdown_event_check())

    def test_transport_redis(self):
        global published_message
        return_value = self.transporter.publish_message()
        self.assertEqual(return_value, None)
        self.assertEqual(published_message, "\n".join([self.test_message] * 8))

    def test_transport_failsafeq(self):
        global published_message
        transport.setFailsafeQueue({"queue1": [[self.test_message]]})
        return_value = self.transporter.publish_message()
        self.assertEqual(return_value, None)
        self.assertEqual(published_message, self.test_message)

    def test_transport_pika_exception(self):
        global published_message
        self.transporter.channel.basic_publish = mock_publish_exception
        return_value = self.transporter.publish_message()
        self.assertEqual(return_value, None)
        self.assertEqual(transport.getFailsafeQueue()["queue1"][0],
                         [self.test_message] * 8)

    def test_transport_stopping(self):
        self.transporter.stopping = True
        return_value = self.transporter.publish_message()
        self.assertEqual(return_value, None)
