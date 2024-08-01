import fcntl
import logging
import os
import socket
import struct
import subprocess
import time

import yaml


def set_destructive(payload: dict) -> dict:
    """CUP packet rewrites client config from scratch"""
    payload.update(FORCE=True)
    return payload


def get_mac(network_iface: str) -> str:
    """Get MAC-address of given network interface"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        info = fcntl.ioctl(s.fileno(),
                           0x8927,
                           struct.pack('256s', bytes(network_iface, 'utf-8')[:15]))
        return ''.join('%02x' % b for b in info[18:24])
    except OSError as e:
        raise OSError(f"wrong name for external network interface given\n\n{e}")


def get_ip(network_iface: str) -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        addr = socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', bytes(network_iface[:15], 'utf-8')))[20:24])
        if not addr:
            raise OSError
    except OSError:
        # ok, try with subprocess
        addr = subprocess.check_output(['hostname', '-I']).rstrip().decode()

    if addr and addr != '':
        logging.debug(f'get IP on {network_iface}: {addr}')
        return addr
    else:
        logging.error('!cannot acquire IP!')
        return '127.0.0.2'


def get_config(file_name: str) -> dict:
    """ Get default config from file """
    with open(os.path.join(os.getcwd(), file_name)) as f:
        try:
            return yaml.load(f, Loader=yaml.BaseLoader)
        except Exception:
            raise


class Event:
    """Internal queue event"""

    def __init__(self, _type, cmd: str = None, data: dict = None):
        self.type = _type
        self.cmd = cmd
        self.data = data

    def __repr__(self):
        return f'[ EVENT of type {self.type} with command {self.cmd} data: {self.data} ]'


def make_event(_type, cmd: str = None, data: dict = None) -> Event:
    """ event making interface """
    try:
        event = Event(_type, cmd, data)
        return event
    except Exception:
        raise


class FileLock:
    """Locking file

       TODO: should use fcntl.flock
    """

    locked = None

    def __init__(self, file_to_lock: str, timeout=1):
        self.timeout = timeout
        self.lock_path = os.path.abspath(file_to_lock) + '.lock'

    def acquire(self):
        """Acquire file lock"""
        idx = 0
        while not self.locked:
            try:
                time.sleep(.1)
                with open(self.lock_path, 'w+') as fl:
                    content = fl.read().strip()
                    if content != '1':
                        fl.write('1')
                        self.locked = True
                        return self.locked
                idx += .1
                if idx >= self.timeout:
                    raise Exception('failed to acquire file lock by timeout')
            except Exception:
                raise

    def release(self):
        """ Release file lock """
        with open(self.lock_path, 'w') as fl:
            fl.write('0')
        self.locked = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *err):
        self.release()
        return
