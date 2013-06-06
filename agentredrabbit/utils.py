try:
    import logging
    import os
    import redis
    import smtplib

    from email.mime.text import MIMEText
except ImportError, err:
    print "ImportError", err
    import sys
    sys.exit(1)

log_format = ('%(levelname) -8s %(asctime)s %(name) 25s %(funcName) '
              '-30s %(lineno) -5d: %(message)s')
log = logging.getLogger(__name__)


class RedisHelper(object):
    def __init__(self, host="127.0.0.1", port=6379):
        self.host = host
        self.port = int(port)
        self.redis = None

    def connect(self):
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
        return self.connect()

    def pop(self, queue, timeout=5):
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
        """This method must be called by a thread after acquiring a lock.
           Method would return data, error."""
        if self.redis is None:
            error = self.connect()
            if error:
                return None, error
        try:
            max_len = self.length(queue)
            if max_len == None:
                return None, True
            if max_len == 0:
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
        log.info("Chunk popped, size=%s", chunk_size)
        return data[0], not data[1]


class EmailHelper(object):
    def __init__(self, agent, sender, receivers):
        self.agent = agent
        self.sender = sender
        self.receivers = receivers.split(",")

    def send(self, subject, message):
        """Sends notification via email"""
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
