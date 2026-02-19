import time

class SimpleCache:
    def __init__(self, default_ttl=3600):
        self._data = {}
        self._default_ttl = default_ttl

    def get(self, key):
        if key in self._data:
            entry = self._data[key]
            if time.time() < entry['expiry']:
                return entry['value']
            else:
                del self._data[key]
        return None

    def set(self, key, value, ttl=None):
        ttl = ttl or self._default_ttl
        self._data[key] = {
            'value': value,
            'expiry': time.time() + ttl
        }

    def clear(self):
        self._data.clear()

# Global cache instance
CACHE = SimpleCache()
