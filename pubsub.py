import datetime
import json
import logging
import ssl
from os import path
import urllib
import urllib.request


import jwt
import paho.mqtt.client as mqtt

import var_protection

mqtt_client = None
public_key = None
device = None


def setup_pubsub(env):
    global api, keydir, mqtt_host
    api = env['api']
    keydir = env['keydir']
    mqtt_host = env['mqtt']
    pass


def read_public_key():
    global public_key
    if public_key is not None:
        return public_key
    file_path = keydir + '/rsa_public.pem'
    with open(file_path, 'r') as fp:
        public_key = fp.read()
    return public_key


def register():
    logging.info('begin device registration')
    url = api + '/v1/devices'
    data = {
        'public_key': read_public_key()
    }
    headers = {
        'Content-Type': 'application/json'
    }
    req = urllib.request.Request(url, json.dumps(data).encode('utf-8'), headers)
    req.method = 'PUT'
    try:
        with urllib.request.urlopen(req) as res:
            result = res.read()
            logging.debug('api result: {}'.format(result))
            body = json.loads(result.decode('utf-8'))
            write_device_file(body)
        return True
    except OSError:
        logging.warning('registration failre by api (URLError)')
        return False
    except TypeError:
        logging.warning('registration failre by api (TypeError)')
        return False


def load_device_file():
    global device
    file_path = keydir + '/device.json'
    if not path.exists(file_path):
        return
    with open(file_path) as fp:
        device = json.loads(fp.read())
    return device


def write_device_file(body):
    global device
    file_path = keydir + '/device.json'
    var_protection.unlock()
    with open(file_path, 'w') as fp:
        fp.write(json.dumps(body))
    var_protection.lock()
    device = body


def register_if_needed():
    load_device_file()
    if device is not None:
        return True
    return register()


def create_jwt():
    project_id = device['project_id']
    private_key_file = keydir + '/rsa_private.pem'
    algorithm = 'RS256'

    token = {
        'iat': datetime.datetime.utcnow(),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=60),
        'aud': project_id
    }

    # Read the private key file.
    with open(private_key_file, 'r') as f:
        private_key = f.read()

    logging.debug('Creating JWT using {} from private key file {}'.format(
        algorithm, private_key_file))

    return jwt.encode(token, private_key, algorithm=algorithm)


def connect():
    global mqtt_client
    logging.info('MQTT connecting: {}:{} / {}'.format(mqtt_host['host'], mqtt_host['port'], device['topic']))

    roots_pem_path = path.dirname(__file__) + '/roots.pem'
    mqtt_client = mqtt.Client(client_id=device['topic'])
    mqtt_client.username_pw_set(username='unused', password=create_jwt())
    mqtt_client.tls_set(ca_certs=roots_pem_path, tls_version=ssl.PROTOCOL_TLSv1_2)

    mqtt_client.on_connect = on_connect
    mqtt_client.on_publish = on_publish
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message

    mqtt_client.connect(mqtt_host['host'], mqtt_host['port'], keepalive=60)
    mqtt_client.subscribe('/devices/{}/config'.format(device['device_id']), qos=1)
    mqtt_client.publish('/devices/{}/state'.format(device['device_id']), payload='{"state":"connect"}', qos=1)


def loop():
    if mqtt_client is not None:
        mqtt_client.loop()


def disconnect():
    global mqtt_client
    if mqtt_client is not None:
        mqtt_client.disconnect()
        mqtt_client = None


# noinspection PyUnusedLocal
def on_connect(client, userdata, flags, rc):
    logging.info('MQTT on_connect')


# noinspection PyUnusedLocal
def on_disconnect(client, userdata, rc):
    logging.info('MQTT on_disconnect')
    disconnect()


# noinspection PyUnusedLocal
def on_publish(client, userdata, mid):
    logging.info('MQTT on_publish: {}'.format(mid))


# noinspection PyUnusedLocal
def on_message(client, userdata, message):
    logging.info('MQTT on_message: {} -> {}'.format(message.topic, message.payload))
