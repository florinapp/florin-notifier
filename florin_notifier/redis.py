import json
import os
from redis import Redis


DAY = 24 * 60 * 60


REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')

REDIS_PORT = os.getenv('REDIS_PORT', 6379)

r = Redis(host=REDIS_HOST, port=REDIS_PORT)


def store(key, obj):
    r.set(key, json.dumps(obj), ex=1*DAY)


def retrieve(key):
    return json.loads(r.get(key))


def get_sorted_keys(key_pattern):
    return sorted(r.keys(key_pattern))
