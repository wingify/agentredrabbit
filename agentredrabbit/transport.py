# -*- coding: utf-8 -*-
try:
    import heapq
    import pika
    import redis
    import logging
    import json
    import smtplib
    import socket
    import threading
    import time
    import urllib

    from utils import RedisHelper, EmailHelper
except ImportError, err:
    print "ImportError", err
    import sys
    sys.exit(1)

log = logging.getLogger(__name__)

# Failsafe heap queue
failsafeq = None


def getFailsafeQueue():
    global failsafeq
    return failsafeq


def setFailsafeQueue(queue):
    global failsafeq
    failsafeq = queue


class Transporter(threading.Thread):
    def __init__(self, threadnum, lock, config, queue, shutdown_event):
        threading.Thread.__init__(self)
        self.threadnum = threadnum
        self.lock = lock
        self.config = config
        self.queue = queue
        self.shutdown_event = shutdown_event

        self.redis_queue = "queue:%s_redis" % self.queue
        self.redis = RedisHelper(config["redis_host"],
                                 config["redis_port"])
        self.mailer = EmailHelper(config["agent"],
                                  config["sender_email"],
                                  config["receiver_email"])

        self.tag = "%s-%s#%s" % (config["agent"], self.queue, self.threadnum)
        self.exchange = config["rabbit_exchange"]
        self.exchange_type = config["rabbit_exchange_type"]
        self.routing_key = "%s.%s.log" % (socket.gethostname(), self.queue)
        self.publish_interval = config["publish_interval"]
        self.message_header = {"node": socket.gethostname(),
                               "queue": self.queue,
                               "tag": self.tag}

        self.amqp_url = ("amqp://%s:%s@%s:%s/%s?connection_attempts=3&"
                         "heartbeat_interval=600&socket_timeout=300" %
                         (config["rabbit_user"], config["rabbit_passwd"],
                          config["rabbit_host"], config["rabbit_port"],
                          urllib.quote(config["rabbit_vhost"], "")))

        self.connection = None
        self.channel = None
        self.deliveries = []
        self.acked = 0
        self.nacked = 0
        self.message_number = 0
        self.stopping = False
        self.closing = False

    def connect(self):
        log.debug("(%s) Connecting to %s", self.tag, self.amqp_url)
        conn = None
        try:
            conn = pika.SelectConnection(pika.URLParameters(self.amqp_url),
                                         self.on_connection_open,
                                         stop_ioloop_on_close=False)
        except (pika.exceptions.AMQPConnectionError, Exception), err:
            log.error("(%s) AMQP conn error: %s" % (self.tag, err))
        return conn

    def close_connection(self):
        log.debug("(%s) Closing connection", self.tag)
        self.closing = True
        self.connection.close()

    def add_on_connection_close_callback(self):
        log.debug("(%s) Adding connection close callback", self.tag)
        self.connection.add_on_close_callback(self.on_connection_closed)

    def on_connection_closed(self, connection, reply_code, reply_text):
        self.channel = None
        if self.closing:
            self.connection.ioloop.stop()
        else:
            log.warning("(%s) Connection closed, reopening in 5s: (%s) %s",
                        self.tag, reply_code, reply_text)
            self.connection.add_timeout(5, self.reconnect)

    def on_connection_open(self, unused_connection):
        log.info("(%s) Connection opened", self.tag)
        self.add_on_connection_close_callback()
        self.open_channel()

    def reconnect(self, tries=0):
        if self.connection is not None:
            self.connection.ioloop.stop()

        if self.shutdown_event_check():
            return

        if not self.stopping:
            log.info("(%s) Connecting to broker", self.tag)
            connection = self.connect()
            if connection is not None:
                self.connection = self.connect()
                self.connection.add_timeout(5, self.signal_checkup)
                self.connection.ioloop.start()
            else:
                log.info("(%s) Failed reconnect, retrying", self.tag)
                if tries < 10:
                    self.reconnect(tries + 1)
                else:
                    self.mailer.send("(%s) RMQ reconnection failed" % self.tag,
                                     "Failed to reconnect to the broker")

    def add_on_channel_close_callback(self):
        log.debug("(%s) Adding channel close callback", self.tag)
        self.channel.add_on_close_callback(self.on_channel_closed)

    def on_channel_closed(self, channel, reply_code, reply_text):
        log.warning("(%s) Channel %i was closed: (%s) %s",
                    self.tag, channel, reply_code, reply_text)
        if not self.closing:
            self.connection.close()

    def on_channel_open(self, channel):
        log.debug("(%s) Channel opened", self.tag)
        self.channel = channel
        self.add_on_channel_close_callback()
        self.setup_exchange(self.exchange)

    def setup_exchange(self, exchange_name):
        log.debug("(%s) Declaring exchange %s", self.tag, exchange_name)
        self.channel.exchange_declare(self.on_exchange_declareok,
                                      exchange_name,
                                      self.exchange_type,
                                      durable=True)

    def on_exchange_declareok(self, unused_frame):
        log.debug("(%s) Exchange declared", self.tag)
        self.setup_queue(self.queue)

    def setup_queue(self, queue_name):
        log.debug("(%s) Declaring queue %s", self.tag, queue_name)
        self.channel.queue_declare(self.on_queue_declareok, queue_name,
                                   durable=True)

    def on_queue_declareok(self, method_frame):
        log.debug("(%s) Binding %s to %s with %s", self.tag, self.exchange,
                  self.queue, self.routing_key)
        self.channel.queue_bind(self.on_bindok, self.queue,
                                self.exchange, self.routing_key)

    def on_delivery_confirmation(self, method_frame):
        confirmation_type = method_frame.method.NAME.split(".")[1].lower()
        log.debug("(%s) Received %s for delivery tag: %i",
                  self.tag, confirmation_type,
                  method_frame.method.delivery_tag)
        if confirmation_type == "ack":
            self.acked += 1
        elif confirmation_type == "nack":
            self.nacked += 1
        self.deliveries.remove(method_frame.method.delivery_tag)
        log.info("(%s) Published %i messages, %i have yet to be confirmed, "
                 "%i were acked and %i were nacked",
                 self.tag, self.message_number, len(self.deliveries),
                 self.acked, self.nacked)

    def enable_delivery_confirmations(self):
        log.info("(%s) Issuing Confirm.Select RPC command", self.tag)
        self.channel.confirm_delivery(self.on_delivery_confirmation)

    def publish_message(self):
        if self.stopping:
            return

        message, error = None, False
        global failsafeq
        with self.lock:
            if len(failsafeq[self.queue]) > 0:
                try:
                    message = heapq.heappop(failsafeq[self.queue])
                except heapq.IndexError:
                    error = True
            else:
                try:
                    message, error = self.redis.chunk_pop(self.redis_queue)
                except Exception, err:
                    sub = "(%s) Unknown chunk_pop Redis error" % self.tag
                    msg = "Exception on Redis::chunk_pop: %s" % err
                    log.error("%s: %s", sub, msg)
                    self.mailer.send(sub, msg)

        if error:
            if message is not None and len(message) > 0:
                sub = "(%s) Unexpected Redis chunk pop issue" % self.tag
                msg = "chunk_pop returned error and message:\n%s" % message
                with self.lock:
                    heapq.heappush(failsafeq[self.queue], message)
                log.error("%s: %s", sub, msg)
                self.mailer.send(sub, msg)
        else:
            if message is not None and len(message) > 0:
                properties = pika.BasicProperties(app_id=self.tag,
                                                  delivery_mode=2,
                                                  headers=self.message_header)
                try:
                    self.channel.basic_publish(self.exchange,
                                               self.routing_key,
                                               "\n".join(message),
                                               properties=properties,
                                               mandatory=True)
                except (pika.exceptions.ChannelClosed, Exception), err:
                    log.error("(%s) Publish error, maybe channel closed: %s",
                              self.tag, err)
                    with self.lock:
                        heapq.heappush(failsafeq[self.queue], message)
                else:
                    self.message_number += 1
                    self.deliveries.append(self.message_number)
                    log.info("Published message # %i", self.message_number)
        self.schedule_next_message()

    def schedule_next_message(self):
        if self.stopping:
            return
        log.debug("Scheduling next message for %0.1f seconds",
                  self.publish_interval)
        self.connection.add_timeout(self.publish_interval,
                                    self.publish_message)

    def start_publishing(self):
        log.info("Issuing consumer related RPC commands")
        self.enable_delivery_confirmations()
        self.schedule_next_message()

    def on_bindok(self, unused_frame):
        log.debug("(%s) Queue bound", self.tag)
        self.start_publishing()

    def close_channel(self):
        log.debug("(%s) Closing the channel", self.tag)
        if self.channel:
            self.channel.close()

    def open_channel(self):
        log.debug("(%s) Creating a new channel", self.tag)
        self.connection.channel(on_open_callback=self.on_channel_open)

    def run(self):
        log.info("(%s) Starting transporting thread", self.tag)
        while not self.shutdown_event.is_set():
            self.transport()
        log.info("(%s) Deliveries: %s", self.tag, self.deliveries)
        # FIXME: what to do with unack messags?

    def transport(self):
        if self.shutdown_event_check():
            return
        try:
            self.reconnect()
        except Exception, err:
            log.error("(%s) Transporter run() error: %s", self.tag, err)

    def signal_checkup(self):
        log.debug("(%s) Performing signal checkup" % self.tag)
        if self.shutdown_event_check():
            return
        self.connection.add_timeout(5, self.signal_checkup)

    def shutdown_event_check(self):
        if self.shutdown_event.is_set():
            log.info("(%s) Shutdown event set, stopping", self.tag)
            self.stop()
            return True
        return False

    def stop(self):
        if self.stopping and self.closing:
            return
        log.info("(%s) Stopping", self.tag)
        self.stopping = True
        self.close_channel()
        self.close_connection()
        if self.connection is not None:
            self.connection.ioloop.start()
        log.info("(%s) Stopped", self.tag)
