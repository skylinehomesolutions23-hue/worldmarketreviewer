_cache = {}

def set(key, value, ttl=60):
    _cache[key] = value

def get(key):
    return _cache.get(key)
