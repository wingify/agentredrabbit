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
    """
    Method mocks RabbitMQ's basic_publish and puts sent msg into a global
    variable published_message
    """
    global published_message
    published_message = msg


def mock_publish_exception(exchange, key, msg, properties, mandatory):
    """
    Method mocks RabbitMQ's basic_publish which throws a ChannelClosed
    exception to simulate a channel failure or conn. failure
    """
    raise pika.exceptions.ChannelClosed


class TransportTests(unittest.TestCase):
    """
    Bunch of unit tests to test transport.py
    """
    def setUp(self):
        """
        Creates a Transporter object
        Mocks Redis, channel, schedule_next_message and basic_publish
        """
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
        """
        test_delivery_confirmation_ack
        Tests delivery confirmation method when a confirms frame is sent from
        RabbitMQ server;
            - We mock a confirms frame
            - Assert that delivery_tag does not exist in deliveries
            - We append the delivery_tag to simulate a msg was sent
            - Assert that delivery_tag exists in deliveries
            - Run the on_delivery_confirmation
            - Assert that delivery_tag does not exist in deliveries
        """
        frame = Mock()
        frame.method.NAME = "something.ACK.somethingelse"
        frame.method.delivery_tag = 1234
        self.assertFalse(1234 in self.transporter.deliveries)
        self.transporter.deliveries.append(1234)
        self.assertTrue(1234 in self.transporter.deliveries)
        self.transporter.on_delivery_confirmation(frame)
        self.assertFalse(1234 in self.transporter.deliveries)

    def test_shutdown_event_check(self):
        """
        test_shutdown_event_check
        Checks behavior of shutdown_event_check() when the event object is set;
            - We mock the stop() method
            - Publishing is set to True and check behavior
            - Publishing is set to False and check behavior
        """
        self.transporter.stop = Mock()
        self.transporter.shutdown_event.set()
        self.transporter.publishing = True
        self.assertFalse(self.transporter.shutdown_event_check())
        self.transporter.publishing = False
        self.assertTrue(self.transporter.shutdown_event_check())

    def test_transport_redis(self):
        """
        test_transport_redis
        Tests publish_message when there is some data in Redis;
            - Redis, channel etc. are mocked in setUp()
            - Runs publish_message(),  the case where redis.chunk_pop returns
              some chunk of data.
            - Checks return_value
            - Checks that published_message is a newline separate chunked data
        """
        global published_message
        return_value = self.transporter.publish_message()
        self.assertEqual(return_value, None)
        self.assertEqual(published_message, "\n".join([self.test_message] * 8))

    def test_transport_failsafeq(self):
        """
        test_transport_failsafeq
        Tests publish_message when there is some data in failsafeq;
            - Redis, channel etc. are mocked in setUp()
            - Set some fake queue in the failsafeq
            - Runs publish_message()
            - Checks that returned value matches
        """
        global published_message
        transport.setFailsafeQueue({"queue1": [[self.test_message]]})
        return_value = self.transporter.publish_message()
        self.assertEqual(return_value, None)
        self.assertEqual(published_message, self.test_message)

    def test_transport_pika_exception(self):
        """
        test_transport_pika_exception
        Tests a case when AMQP exception occurs while transporting;
            - Redis, channel etc. are mocked in setUp()
            - publish_message() on exception should push data to failsafeq
            - Check that chunk landed in the failsafeq
        """
        global published_message
        self.transporter.channel.basic_publish = mock_publish_exception
        return_value = self.transporter.publish_message()
        self.assertEqual(return_value, None)
        self.assertEqual(transport.getFailsafeQueue()["queue1"][0],
                         [self.test_message] * 8)

    def test_transport_stopping(self):
        """
        test_transport_stopping
        Checks the case when ioloop is stopped;
            - Set stopping to True
            - Check that publish_message() returns None
            - Check that publish_message() published no message
        """
        global published_message
        self.transporter.stopping = True
        published_message = None
        return_value = self.transporter.publish_message()
        self.assertEqual(return_value, None)
        self.assertEqual(published_message, None)
