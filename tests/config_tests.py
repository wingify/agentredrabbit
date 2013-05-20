try:
    import unittest2 as unittest
except ImportError:
    import unittest

import mock
from agentredrabbit import config


class ConfigTests(unittest.TestCase):
    def test_ReadConfig(self):
        cfg = config.ReadConfig()
        self.assertEqual(cfg["host"], "localhost")
        self.assertEqual(cfg["port"], "5672")
        self.assertEqual(cfg["username"], "guest")
        self.assertEqual(cfg["password"], "guest")
        self.assertEqual(cfg["vhost"], "/")
