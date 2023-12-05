import base64
from datetime import datetime, timedelta
import json
import pyiotown.post_process
import pyiotown.get
import pyiotown.delete
import pyiotown.post
import redis
from urllib.parse import urlparse
import math

TAG = 'LHT65N'

def init(url, pp_name, mqtt_url, redis_url, dry_run=False):
    global iotown_url, iotown_token
    
    url_parsed = urlparse(url)
    iotown_url = f"{url_parsed.scheme}://{url_parsed.hostname}" + (f":{url_parsed.port}" if url_parsed.port is not None else "")
    iotown_token = url_parsed.password
    
    if redis_url is None:
        print(f"Redis is required for EdgeEye.")
        return None

    global r
    
    try:
        r = redis.from_url(redis_url)
        if r.ping() == False:
            r = None
            raise Exception('Redis connection failed')
    except Exception as e:
        raise(e)
    
    return pyiotown.post_process.connect_common(url, pp_name, post_process, mqtt_url, dry_run=dry_run)
    
def post_process(message, param=None):
    raw = base64.b64decode(message['meta']['raw'])

    fcnt = message["meta"].get("fCnt")

    mutex_key = f"PP:{TAG}:MUTEX:{message['grpid']}:{message['nid']}:{fcnt}"
    
    lock = r.set(mutex_key, 'lock', ex=30, nx=True)
    print(f"[{TAG}] lock with '{mutex_key}': {lock}")
    if lock != True:
        return None

    if message['meta']['fPort'] == 2:
        bat = int.from_bytes(raw[0:2], 'big', signed=False)
        message['data']['battery_mV'] = bat & 0x3FFF

        message['data']['temperature_builtin'] = int.from_bytes(raw[2:4], 'big', signed=True) / 100
        message['data']['humidity_builtin'] = int.from_bytes(raw[4:6], 'big', signed=False) / 10

        ext = raw[6]
        if ext == 0x01:
            val = int.from_bytes(raw[7:9], 'big', signed=False)
            if val & 0x8000 == 1:
                val = val - 65536
            message['data']['temperature_ext'] = val / 100
        return message
    else:
        return None
