"""
Provides reusable utilities and helper classes.
"""

import logging
import os
import redis
import smtplib

from email.mime.text import MIMEText

log_format = ('%(levelname) -8s %(asctime)s %(name) 25s %(funcName) '
              '-30s %(lineno) -5d: %(message)s')
log = logging.getLogger(__name__)


class RedisHelper(object):
    """
    Redis helper utility class which provides a higher level interface to
    perform Redis operations such as connect, pop, push.
    """
    def __init__(self, host="127.0.0.1", port=6379):
        """
        RedisHelper class initializer
        @param host: IP or hostname of the Redis server. Default 127.0.0.1
        @param port: Port of the Redis server. Default 6379
        """
        self.host = host
        self.port = int(port)
        self.redis = None

    def connect(self):
        """
        Method provides mechanism to connect to a Redis Server.
        First it tries to connect to a local unix socket, assuming this will
        be used on localhost Redis server. On failure it tries to connect to
        Redis server on provided host:port
        """
        error = False
        try:
            self.redis = redis.Redis(unix_socket_path='/tmp/redis.sock')
            self.redis.info()
        except (redis.exceptions.ConnectionError, Exception), err:
            try:
                log.debug("Connection failed on unix socket, trying socket")
                self.redis = redis.StrictRedis(host=self.host,
                                               port=self.port, db=0)
                self.redis.info()
            except Exception, err:
                self.redis = None
                error = True
                log.error("Redis Error: %s", err)
        return error

    def recover(self):
        """
        Method connects to Redis server. This should be called in case of Redis
        connection failure
        """
        return self.connect()

    def pop(self, queue, timeout=5):
        """
        Method does a blocking pop on Redis list which is seen as a fifo queue.
        On failure it returns None, else the popped value.
        @param queue: Name of the Redis list
        @param timeout: Timeout duration for blpop operation. Default 5s
        """
        if self.redis is None:
            error = self.connect()
            if error:
                return None
        try:
            data = self.redis.blpop(queue, timeout)
        except Exception, err:
            log.error("Redis (pop) error: %s", err)
            return None
        return data

    def push(self, queue, data):
        """
        Method does a lpush operation on Redis list. On exception, it returns
        True else returns False.
        @param queue: Name of the Redis list
        @param data: The data that needs to be pushed in the queue
        """
        if self.redis is None:
            error = self.connect()
            if error:
                return True
        try:
            data = self.redis.lpush(queue, data)
        except Exception, err:
            log.error("Redis (push) error: %s", err)
            return True
        return False

    def length(self, queue):
        """
        Method gives length of a Redis list
        @param queue: Name of the Redis queue
        """
        if self.redis is None:
            error = self.connect()
            if error:
                return None
        try:
            length = self.redis.llen(queue)
        except Exception, err:
            log.error("Redis, (llen) error: %s", err)
            return None
        return length

    def chunk_pop(self, queue, chunk_size=1000):
        """
        Method returns a chunk of popped values from a Redis list with a max
        chunk size of 1000. This method must be called by a thread or worker
        after acquiring a lock. Method returns multiple variables data, error.
        @param queue: Name of the Redis list
        @param chunk_size: Maximum size of the chunk. Default 1000
        """
        if self.redis is None:
            error = self.connect()
            if error:
                return None, error
        try:
            max_len = self.length(queue)
            if max_len is None:
                return None, True
            if max_len is 0:
                return None, False
            if chunk_size > max_len:
                chunk_size = max_len
            pipe = self.redis.pipeline()
            pipe.lrange(queue, 0, chunk_size - 1)
            pipe.ltrim(queue, chunk_size, -1)
            data = pipe.execute()
        except Exception, err:
            log.error("Redis (pop) error: %s", err)
            return None, True
        log.debug("Redis chunk popped, size=%s", chunk_size)
        return data[0], not data[1]


class EmailHelper(object):
    """
    Email helper utility class which provides an interface to send email
    """
    def __init__(self, agent, sender, receivers):
        """
        Initializer for EmailHelper
        @param agent: Consumer tag or identifier
        @param sender: Email of the sender
        @param receivers: Comma separated emails of the receivers
        """
        self.agent = agent
        self.sender = sender
        self.receivers = receivers.split(",")

    def send(self, subject, message):
        """
        Sends email with a subject and a message. On exception, method silently
        logs the error in the error logs.
        @param subject: Subject of the email
        @param message: Message body of the email
        """
        sender = self.sender
        receivers = self.receivers
        agent = self.agent

        msg = MIMEText(message)
        msg["Subject"] = "%s: %s" % (agent, subject)
        msg["From"] = sender
        msg["To"] = ", ".join(receivers)

        try:
            smtpObj = smtplib.SMTP("localhost")
            smtpObj.sendmail(sender, receivers, msg.as_string())
            smtpObj.quit()
        except smtplib.SMTPException, err:
            log.error("Unable to send email due to: %s" % err)
        except Exception, err:
            log.error("Unable to send email due to: %s" % err)
