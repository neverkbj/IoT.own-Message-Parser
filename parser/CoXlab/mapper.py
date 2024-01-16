import base64
from datetime import datetime, timedelta
import pyiotown.post_process
import redis
from urllib.parse import urlparse
import json

TAG = 'Mapper'

def init(url, pp_name, mqtt_url, redis_url, dry_run=False):
    global iotown_url, iotown_token
    
    url_parsed = urlparse(url)
    iotown_url = f"{url_parsed.scheme}://{url_parsed.hostname}" + (f":{url_parsed.port}" if url_parsed.port is not None else "")
    iotown_token = url_parsed.password
    
    if redis_url is None:
        print(f"Redis is required for {TAG}.")
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
    try:
        params = json.loads('{' + param + '}')
    except:
        raise Exception('param format error')

    for k in params.keys():
        if type(params[k]) is not list or len(params[k]) != 4:
            raise Exception('param format error')
    
    #Data MUTEX
    mutex_key = f"PP:{TAG}:MUTEX:{message['grpid']}:{message['nid']}:{message['key']}"
    lock = r.set(mutex_key, 'lock', ex=10, nx=True)
    print(f"[{TAG}] lock with '{mutex_key}': {lock}")
    if lock != True:
        return None

    mapping = {}
    for k in params.keys():
        if k in message['data'].keys():
            try:
                in_min = float(params[k][0])
                in_max = float(params[k][1])
                out_min = float(params[k][2])
                out_max = float(params[k][3])
            
                original = message['data'][k]
                message['data'][k] = (original - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
            except:
                raise Exception(f"param error on for '{k}'")

    r.delete(mutex_key)
    return message
