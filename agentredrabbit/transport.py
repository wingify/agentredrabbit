try:
    import heapq
    import pika
    import redis
    import smtplib
    import socket
    import threading
    import time

    from logger import log
    from email.mime.text import MIMEText
    from watchdog.events import FileSystemEventHandler
except ImportError, err:
    print "ImportError", err
    import sys
    sys.exit(1)

# Grace shutdown flag
pid_file_exists = False

# Failed messages
failsafeq = None


def getPidFileExists():
    global pid_file_exists
    return pid_file_exists


def setPidFileExists(flag):
    global pid_file_exists
    pid_file_exists = flag


def getFailsafeQueue():
    global failsafeq
    return failsafeq


def setFailsafeQueue(queue):
    global failsafeq
    failsafeq = queue


class PidFileEventHandler(FileSystemEventHandler):
    def __init__(self, pid_file, observer):
        self.pid_file = pid_file
        self.observer = observer

    def on_deleted(self, event):
        log.info("Event: " + repr(event))
        if event.is_directory:
            return
        if event.src_path == self.pid_file:
            log.info("Shutdown signal received, stopping")
            global pid_file_exists
            pid_file_exists = False
            self.observer.stop()


class TransportQueueThread(threading.Thread):
    def __init__(self, lock, threadnum, queue, config):
        threading.Thread.__init__(self)
        self.lock = lock
        self.threadnum = threadnum
        self.config = config
        self.queue = queue
        self.exchange = config["exchange"]
        self.routing_key = "%s.%s.log" % (socket.gethostname(), queue)
        self.redis_queue = "queue:%s_redis" % queue

    def sendEmail(self, subject, message):
        """Sends notification via email"""
        sender = self.config["senderemail"]
        receivers = [self.config["receiveremail"]]

        msg = MIMEText(message)
        msg["Subject"] = "agentredrabbit: %s" % subject
        msg["From"] = socket.gethostname() + sender
        msg["To"] = ", ".join(receivers)

        try:
            smtpObj = smtplib.SMTP('localhost')
            smtpObj.sendmail(sender, receivers, msg.as_string())
            smtpObj.quit()
        except smtplib.SMTPException:
            log.error("[!] Unable to send email")
        except Exception:
            log.debug("[!] sendMail failure due to socket error")

    def getRedis(self):
        """Creates and sets the global redis conn obj"""
        try:
            log.debug("[*] Connecting to Redis on unix socket")
            red = redis.Redis(unix_socket_path='/tmp/redis.sock')
            red.info()
        except redis.exceptions.ConnectionError, err:
            log.debug("[!] Redis conn on unix socket failed")
            log.debug("[*] Connecting Redis on localhost:6379")
            red = redis.StrictRedis(host="localhost", port=6379, db=0)
        return red

    def popFromRedis(self, red):
        data = None
        err = False
        try:
            if red is None:
                red = self.getRedis()
            data = red.blpop(self.redis_queue, timeout=5)
        except redis.exceptions.ConnectionError:
            err = True
        return data, red, err

    def pushToRedis(self, red, payload):
        err = False
        try:
            if red is None:
                red = self.getRedis()
            red.lpush(self.redis_queue, payload)
        except redis.exceptions.ConnectionError:
            err = True
        return red, err

    def getRabbit(self):
        """Creates and returns rabbit connection obj"""
        err = False
        try:
            log.debug("[*] Connecting to RabbitMQ: " + repr(self.config))
            credentials = pika.PlainCredentials(self.config["username"],
                                                self.config["password"])
            params = pika.ConnectionParameters(host=self.config["host"],
                                               port=int(self.config["port"]),
                                               virtual_host=
                                               self.config["vhost"],
                                               credentials=credentials,
                                               heartbeat_interval=600)
            connection = pika.BlockingConnection(params)
        except pika.exceptions.AMQPConnectionError:
            err = True
            connection = None
            log.error("[!] Unable to connect to Rabbit MQ")
        return connection, err

    def publishToRabbit(self, rabbit, channel, payload):
        pushback = False
        try:
            if rabbit is None or channel is None:
                rabbit, err = self.getRabbit()
                if err or rabbit is None:
                    subject = "Unable to get Rabbit connection"
                    message = """Unable to get rabbit connection"""
                    self.sendEmail(subject, message)
                    pushback = True
                    return rabbit, channel, pushback
                channel = rabbit.channel()
                channel.confirm_delivery()
                channel.queue_declare(queue=self.queue, durable=True)
                channel.exchange_declare(exchange=self.exchange,
                                         type="topic", durable=True)
                channel.queue_bind(exchange=self.exchange,
                                   queue=self.queue,
                                   routing_key=self.routing_key)
        except Exception:
            rabbit = None
            channel = None
            pushback = True
            self.sendEmail("Publishing to RMQ failed", "Check agent!")
        try:
            if payload and channel:
                props = pika.BasicProperties(content_type="application/json",
                                             delivery_mode=2)
                confirms = channel.basic_publish(exchange=self.exchange,
                                                 routing_key=self.routing_key,
                                                 body=payload,
                                                 mandatory=True,
                                                 properties=props)
                if not confirms:
                    log.info("Confirms failed, pushing back: " + str(confirms))
                    pushback = True
        except pika.exceptions.ChannelClosed, err:
            log.debug("[!] MQ channel close, retrying")
            rabbit = None
            channel = None
            pushback = False  # Avoid duplication for edge cases
        except Exception, err:
            log.error("Unknown exception while pushing to MQ: " + str(err))
            rabbit = None
            channel = None
            pushback = True
        return rabbit, channel, pushback

    def transportMessages(self):
        """The transport agent code that takes stuff from redis and puts in
          rabbitmq"""
        global failsafeq, pid_file_exists
        # Redis vars
        red = None
        redis_retries = 0
        # Rabbit vars
        rabbit = None
        channel = None
        # Data vars
        data = None
        pushback = False
        while True:
            # On err pushback to Redis, failsafe try again with Rabbit
            if data and pushback:
                red, err = self.pushToRedis(red, data[1])
                if err:
                    log.debug("[!] MQ err, pushing back to redis %s" % data[1])
                    red = None
                    time.sleep(4)
                    rabbit, channel, pushback = self.publishToRabbit(rabbit,
                                                                     channel,
                                                                     data[1])
                    if pushback:
                        with self.lock:
                            heapq.heappush(failsafeq[self.queue], data)
                else:
                    time.sleep(4)

            pushback = False
            # Handle failsafeq items
            with self.lock:
                failsafeqlen = len(failsafeq[self.queue])
                if failsafeqlen > 0:
                    err = False
                    for i in range(failsafeqlen):
                        try:
                            data = heapq.heappop(failsafeq[self.queue])
                        except heapq.IndexError:
                            err = True  # We should never reach here
                        if err:
                            log.info("[!] heapq error, we ought not be here")
                            break
                        rabbit, channel, err = self.publishToRabbit(rabbit,
                                                                    channel,
                                                                    data[1])
                        if err:
                            heapq.heappush(failsafeq[self.queue], data)
                            break

            # On shutdown signal, return to exit the thread
            if pid_file_exists is False:
                return

            # Read from Redis
            data, red, err = self.popFromRedis(red)

            # On error send notification, sleep and retry
            if err:
                data = None
                red = None
                log.info("[!] Redis %s conn err retry=%d" % (self.redis_queue,
                                                             redis_retries))
                if redis_retries % 20 == 0:
                    subject = "agentredrabbit: redis retry #%d" % redis_retries
                    message = """agentredrabbit is having issues, failed to
                    connect to Redis, retry=%d at %s""" % (redis_retries,
                                                           time.asctime())
                    self.sendEmail(subject, message)
                redis_retries += 1
                time.sleep(4)
                continue
            else:
                redis_retries = 0

            # Looks like Redis had a timeout, continue
            if data is None:
                time.sleep(4)
                continue

            # Write to Rabbit
            rabbit, channel, pushback = self.publishToRabbit(rabbit,
                                                             channel,
                                                             data[1])
            if not pushback:
                data = None

    def run(self):
        log.info("Starting agent thread #%d(%s)" % (self.threadnum,
                                                    self.queue))
        self.transportMessages()
        log.info("Exiting agent thread #%d(%s)" % (self.threadnum, self.queue))
        return 0
