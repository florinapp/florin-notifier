import json
from redis import Redis


DAY = 24 * 60 * 60


r = Redis()


def store(key, obj):
    r.set(key, json.dumps(obj), ex=1*DAY)


def retrieve(key):
    return json.loads(r.get(key))


def get_sorted_keys(key_pattern):
    return sorted(r.keys(key_pattern))
