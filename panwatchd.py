#!/usr/bin/env python
import argparse
import logging
import subprocess
import time
import os
import sys
import yaml
import pubsub
import var_protection

last_pan_status = 2


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--env')
    parser.add_argument('--daemon', action='store_true')
    parser.add_argument('-d', '--debug', action='store_true')
    return parser.parse_args()


def load_env_yaml(input_args):
    env_file = input_args.env if 'env' in input_args else 'env.yaml'
    with open(env_file) as f:
        data = yaml.load(f)
    return data


def pan_status():
    # 0: connected / 1: wait DHCP / 2: disconnected
    result = subprocess.call(env['cmd_pan_status'] + ' > /dev/null', shell=True)
    return result


def check_pan_status():
    global last_pan_status
    new_status = pan_status()
    if new_status != last_pan_status:
        logging.debug('change status {} to {}'.format(last_pan_status, new_status))
        if new_status == 0:
            on_connected()
        elif new_status == 2:
            on_disconnected()
    last_pan_status = new_status


def on_connected():
    logging.info('on_connected')
    if pubsub.register_if_needed():
        pubsub.connect()


def on_disconnected():
    logging.info('on_disconnected')
    pubsub.disconnect()


def request_connect():
    if last_pan_status == 2:
        subprocess.call(env['cmd_pan_connect'] + ' > /dev/null', shell=True)


# noinspection PyBroadException
def main_unit():
    logging.info('start')
    index = 0
    while True:
        try:
            if index == 0:
                check_pan_status()
                request_connect()

            if index == 9:
                index = 0
            else:
                index += 1

            pubsub.loop()

        except:
            pass

        finally:
            time.sleep(1)


def daemonize():
    pid = os.fork()
    if pid > 0:
        pid_file = open('/var/run/panwatchd.pid', 'w')
        pid_file.write(str(pid) + "\n")
        pid_file.close()
        sys.exit()
    if pid == 0:
        main_unit()


def setup_debug_logger():
    if args.debug:
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)


if __name__ == '__main__':
    args = parse_args()
    env = load_env_yaml(args)
    pubsub.setup_pubsub(env)
    var_protection.setup_var_protection(env)
    setup_debug_logger()
    if args.daemon:
        while True:
            daemonize()
    else:
        main_unit()
