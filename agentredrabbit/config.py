try:
    import os
    import sys

    from logger import log
    from ConfigParser import ConfigParser
except ImportError, err:
    print("Import error in %s : %s" % (__name__, err))
    import sys
    sys.exit(1)

config_fields = {}
config_fields['host'] = 'localhost'
config_fields['port'] = '5672'
config_fields['username'] = 'guest'
config_fields['password'] = 'guest'
config_fields['vhost'] = ''
config_fields['exchange'] = ''
config_fields['queues'] = 'queue1:queue2:queue3'
config_fields['workers'] = 8
config_fields['senderemail'] = "test@example.com"
config_fields['receiveremail'] = "test@example.com"
config_fields['dumpfile'] = "agentredrabbit.dump"
config_fields['logfile'] = "agentredrabbit.log"

def ReadConfig(config_file):
    global config_fields
    config = ConfigParser()
    section = "agentredrabbit"
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as cfg:
                config.readfp(cfg)
        except IOError, e:
            log.error("Error: config_file not found " + str(e))
    else:
        config.add_section(section)
        for key in config_fields.keys():
            config.set(section, key, config_fields[key])
        with open(config_file, 'w') as cfg:
            config.write(cfg)

    cfg = {}
    for key in config_fields.keys():
        try:
            cfg[key] = config.get(section, key)
        except Exception:
            cfg[key] = config_fields[key]
    return cfg
