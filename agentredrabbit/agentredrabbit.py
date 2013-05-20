#!/usr/bin/env python
# -*- coding: utf-8 -*-
try:
    import logging
    import os
    import pickle
    import sys
    import threading

    from .config import ReadConfig
    from .logger import log
    from .transport import TransportQueueThread, PidFileEventHandler
    from .transport import setFailsafeQueue, getFailsafeQueue
    from .transport import setPidFileExists, getPidFileExists
    from optparse import OptionParser
    from watchdog.observers import Observer
except ImportError, err:
    print "ImportError", err
    import sys
    sys.exit(1)


def main():
    log.setLevel(logging.INFO)
    parser = OptionParser(usage="%prog [-c config] [-s] [-v]",
                          version="%prog %s")
    parser.add_option("-c", "--config",
                      dest="config_file", default=None,
                      help="config file")
    parser.add_option("-s", "--stop",
                      action="store_true", dest="stopdaemon", default=False,
                      help="stop any running agent daemon")
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="increase debug level from INFO to DEBUG")
    (options, args) = parser.parse_args()

    if options.verbose:
        log.setLevel(logging.DEBUG)

    pid_dir = "/tmp/"
    pid_file = pid_dir + "agentredrabbit.pid"
    pid_file_exists = False
    if options.stopdaemon:
        try:
            os.remove(pid_file)
        except Exception:
            log.info("[!] No pid file found, grep ps aux?")
            sys.exit(1)
        log.info("[+] Agent found running, stopping...")
        sys.exit(0)

    cfg_path = "default.conf"
    if options.config_file is not None:
        cfg_path = options.config_file
    config = ReadConfig(cfg_path)
    queues = filter(lambda x: x.strip() != "", config["queues"].split(":"))

    if os.path.exists(pid_file) and os.path.isfile(pid_file):
        try:
            with open(pid_file):
                log.info("Pid file found: " + pid_file)
                log.info("[!] Looks like another agent is running!")
                sys.exit()
        except IOError:
            log.info("[!] IOError in main() IOError, why are we here duh?")
            pass
    else:
        log.info("[+] Writing pid(%d) to file: %s" % (os.getpid(), pid_file))
        f = open(pid_file, "w")
        f.write("%d\n" % os.getpid())
        f.close()
        pid_file_exists = True

    setPidFileExists(pid_file_exists)

    # Apply filesystem event hook on pid_file for graceful shutdown
    observer = Observer()
    event_handler = PidFileEventHandler(pid_file, observer)
    observer.schedule(event_handler, pid_dir)
    observer.start()

    # Failsafe queue handling
    failsafeq = {}
    # Read from dump file if available
    dumpfilename = "safeq-agentredrabbit.dump"
    if os.path.exists(dumpfilename):
        with open(dumpfilename, "rb") as dumpfile:
            failsafeq = pickle.load(dumpfile)
            log.info("[+] Loaded failsafeq: " + str(failsafeq))
    for queue in queues:
        if not queue in failsafeq:
            failsafeq[queue] = []
    setFailsafeQueue(failsafeq)

    # Start threads
    queue_lock = threading.Lock()
    threads = []
    threadcount = int(config["workers"])
    log.info("[+] Starting workers for queues: " + ", ".join(queues))
    for idx, queue in enumerate(queues*threadcount):
        thread = TransportQueueThread(queue_lock, idx, queue, config)
        thread.start()
        threads.append(thread)

    # Wait for threads
    threads.append(observer)
    for thread in threads:
        try:
            thread.join()
        except RuntimeError:
            log.error("Looks like threads exited before they were joined")

    # Gracefully dump internal queue and shutdown
    if getPidFileExists() is False:
        dumpfile = open(dumpfilename, "wb")
        pickle.dump(getFailsafeQueue(), dumpfile)
        dumpfile.close()
        log.info("[*] Shutting down agentredrabbit")
        sys.exit(0)
    log.info("[!] You should not see this message")


if __name__ == "__main__":
    main()
