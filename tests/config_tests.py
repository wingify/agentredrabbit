try:
    import unittest2 as unittest
except ImportError:
    import unittest

import mock
from agentredrabbit import config


class ConfigTests(unittest.TestCase):
    def test_ReadConfig(self):
        cfg = config.ReadConfig()
        self.assertEqual(cfg["rabbit_host"], "127.0.0.1")
        self.assertEqual(cfg["rabbit_port"], "5672")
        self.assertEqual(cfg["rabbit_user"], "guest")
        self.assertEqual(cfg["rabbit_passwd"], "guest")
        self.assertEqual(cfg["rabbit_vhost"], "/")
