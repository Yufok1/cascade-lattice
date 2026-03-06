import time
import unittest

from cascade.proxy import CascadeProxy, AIOHTTP_AVAILABLE


@unittest.skipUnless(AIOHTTP_AVAILABLE, "aiohttp is required for proxy lifecycle tests")
class CascadeProxyLifecycleTests(unittest.TestCase):
    def test_proxy_start_status_stop_cycle(self):
        proxy = CascadeProxy(host="127.0.0.1", port=0, verbose=False)
        status = proxy.start()
        self.assertTrue(status["running"])
        self.assertGreater(proxy.port, 0)

        deadline = time.time() + 2.0
        while time.time() < deadline:
            if proxy.status()["running"]:
                break
            time.sleep(0.05)
        self.assertTrue(proxy.status()["running"])

        stop_status = proxy.stop()
        self.assertFalse(stop_status["running"])
        self.assertFalse(proxy.status()["running"])
