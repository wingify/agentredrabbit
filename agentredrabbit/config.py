"""
Config utility tightly coupled with agentredrabbit
"""

import os
import sys
import logging

from ConfigParser import ConfigParser

log = logging.getLogger(__name__)

config_fields = {}
config_fields['agent'] = 'agentredrabbit'
config_fields['queues'] = 'queue1:queue2:queue3'
config_fields['workers'] = 8
config_fields['publish_interval'] = 1
config_fields['redis_host'] = '127.0.0.1'
config_fields['redis_port'] = '6379'
config_fields['rabbit_host'] = '127.0.0.1'
config_fields['rabbit_port'] = '5672'
config_fields['rabbit_user'] = 'guest'
config_fields['rabbit_passwd'] = 'guest'
config_fields['rabbit_vhost'] = '/'
config_fields['rabbit_exchange'] = 'testx'
config_fields['rabbit_exchange_type'] = 'topic'
config_fields['sender_email'] = "test@example.com"
config_fields['receiver_email'] = "test@example.com,"
config_fields['dump_file'] = "agentredrabbit.dump"
config_fields['log_file'] = "agentredrabbit.log"


def ReadConfig(config_file="/etc/agentredrabbit.conf"):
    """
    Method provides way to read a config file and return a dictionary of
    config keys and its values
    @param config_file: Filesystem path of the config file. Defaults to
    /etc/agentredrabbit.conf
    """
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
        try:
            with open(config_file, 'w') as cfg:
                config.write(cfg)
        except IOError:
            pass

    cfg = {}
    for key in config_fields.keys():
        try:
            cfg[key] = config.get(section, key)
        except Exception:
            cfg[key] = config_fields[key]
    return cfg
