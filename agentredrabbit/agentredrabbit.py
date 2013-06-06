#!/usr/bin/env python
# -*- coding: utf-8 -*-
try:
    import logging
    import os
    import pickle
    import signal
    import sys
    import threading

    from config import ReadConfig
    from utils import log_format
    from transport import Transporter
    from transport import setFailsafeQueue, getFailsafeQueue
    from optparse import OptionParser
except ImportError, err:
    print "ImportError", err
    import sys
    sys.exit(1)

log = logging.getLogger(__name__)
threads = []
shutdown_event = None


def sighandler(signum, frame):
    log.info("Starting graceful shutdown, caught signal #%s" % signum)
    global threads, shutdown_event
    shutdown_event.set()

    for thread in threads:
        thread.join()

    for thread in threads:
        log.info("%s running state = %s" % (thread, thread.is_alive()))


def main():
    log.setLevel(logging.INFO)
    parser = OptionParser(usage="%prog [-c config] [-v]",
                          version="%prog %s")
    parser.add_option("-c", "--config",
                      dest="config_file", default=None,
                      help="config file")
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="increase debug level from INFO to DEBUG")
    (options, args) = parser.parse_args()

    cfg_path = "/etc/agentredrabbit.conf"
    if options.config_file is not None:
        cfg_path = options.config_file
    config = ReadConfig(cfg_path)

    log_level = logging.INFO
    if options.verbose:
        log_level = logging.DEBUG

    logging.basicConfig(filename=config["log_file"], filemode="a",
                        level=log_level, format=log_format)
    logging.getLogger("pika").setLevel(logging.INFO)

    signal.signal(signal.SIGTERM, sighandler)
    signal.signal(signal.SIGINT, sighandler)
    signal.signal(signal.SIGQUIT, sighandler)
    signal.signal(signal.SIGHUP, sighandler)

    queues = filter(lambda x: x.strip() != "", config["queues"].split(":"))

    # Failsafe queue handling
    failsafeq = {}
    # Read from dump file if available
    dumpfilename = config["dump_file"]
    if os.path.exists(dumpfilename):
        with open(dumpfilename, "rb") as dumpfile:
            failsafeq = pickle.load(dumpfile)
            log.info("Loaded failsafeq: " + str(failsafeq))
    for queue in queues:
        if not queue in failsafeq:
            failsafeq[queue] = []
    setFailsafeQueue(failsafeq)

    # Start threads
    global threads, shutdown_event
    shutdown_event = threading.Event()
    qlock = threading.Lock()
    threadcount = int(config["workers"])
    log.info("[+] Starting workers for queues: " + ", ".join(queues))
    for idx, queue in enumerate(queues * threadcount):
        thread = Transporter(idx, qlock, config, queue, shutdown_event)
        thread.start()
        threads.append(thread)

    while not shutdown_event.is_set():
        signal.pause()

    try:
        log.info("Dumping failsafe queue")
        dumpfile = open(dumpfilename, "wb")
        pickle.dump(getFailsafeQueue(), dumpfile)
        dumpfile.close()
    except IOError, err:
        log.error("Dumpiing failsafe queue failed: %s", err)
    log.info("We had a clean shutdown, Bye!")
    sys.exit(0)


if __name__ == "__main__":
    main()
