try:
    import logging
except ImportError, err:
    import sys
    print "ImportError", err
    sys.exit(1)

logging.basicConfig(
    format='%(asctime)s,%(msecs)05.1f (%(funcName)s) %(message)s',
    datefmt='%H:%M:%S')
log = logging.getLogger()
