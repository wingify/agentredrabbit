try:
    import unittest2 as unittest
except ImportError:
    import unittest

import mock
from agentredrabbit import config


class ConfigTests(unittest.TestCase):
    """
    Unit tests for config.py
    """
    def test_ReadConfig(self):
        """
        test_ReadConfig: Tests config utility
        Without giving any cfg file, this tests set of default values
        """
        cfg = config.ReadConfig("/fakefile")
        self.assertEqual(cfg["rabbit_host"], "127.0.0.1")
        self.assertEqual(cfg["rabbit_port"], "5672")
        self.assertEqual(cfg["rabbit_user"], "guest")
        self.assertEqual(cfg["rabbit_passwd"], "guest")
        self.assertEqual(cfg["rabbit_vhost"], "/")
