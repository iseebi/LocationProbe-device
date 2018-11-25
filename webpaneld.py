import argparse
import datetime
import json
import logging
import sys
import urllib
import urllib.request
from os import path

import jwt
import yaml
from flask import Flask, render_template, request

system_name = 'Iseteki CarProbe'
app = Flask(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--env')
    parser.add_argument('--daemon', action='store_true')
    parser.add_argument('-d', '--debug', action='store_true')
    return parser.parse_args()


def load_env_yaml(input_args):
    env_file = input_args.env if input_args.env is not None else path.dirname(__file__) + '/env.yaml'
    with open(env_file) as f:
        data = yaml.load(f)
    return data


def load_device_file():
    file_path = keydir + '/device.json'
    with open(file_path) as fp:
        device = json.loads(fp.read())
    return device


def generate_jwt(device):
    private_key_file = keydir + '/rsa_private.pem'
    with open(private_key_file, 'r') as f:
        private_key = f.read()

    payload = {
        'iat': datetime.datetime.utcnow(),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=60),
    }
    auth_token = jwt.encode(
        payload=payload,
        headers={'kid': device['device_key']},
        key=private_key,
        algorithm='RS256')
    return auth_token.decode('utf-8')


def get_authorization_status(service, auth_token):
    url = '{}/v1/connections/{}'.format(api, service)
    headers = {
        'Authorization': 'Bearer {}'.format(auth_token)
    }
    logging.debug(headers)
    logging.debug(url)
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as res:
            result = res.read()
            logging.debug('api result: {}'.format(result))
            body = json.loads(result.decode('utf-8'))
            return body['connected']
    except OSError:
        logging.warning('{} status indication failre by api (OSError)'.format(service))
        return False
    except TypeError:
        logging.warning('{} status indication failre by api (TypeError)'.format(service))
        return False


def process_status_fragment(service, template):
    device = load_device_file()
    auth_token = generate_jwt(device)
    status = get_authorization_status(service, auth_token)
    callback_uri = '{}services'.format(request.url_root)
    api_url = '{}/oauth/{}/redirect'.format(api, service)
    return render_template(
        template,
        system_name=system_name,
        status=status,
        auth_token=auth_token,
        callback_uri=callback_uri,
        api=api_url)


@app.route('/services')
def services():
    return render_template('services.html', system_name=system_name)


@app.route('/services/line-notify/status')
def line_notify_status():
    return process_status_fragment('line-notify', 'line_notify_status.html')


@app.route('/services/locapos/status')
def locapos_status():
    return process_status_fragment('locapos', 'locapos_status.html')


@app.route('/')
def index():
    return render_template('index.html', system_name=system_name)


def setup_debug_logger():
    if args.debug:
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        # noinspection SpellCheckingInspection
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)


if __name__ == "__main__":
    args = parse_args()
    env = load_env_yaml(args)
    keydir = env['keydir']
    api = env['api']
    setup_debug_logger()
    app.run(debug=(not args.debug), host='0.0.0.0', port=env['webpanel_port'])
