import os
import yaml
import time
import logging
import subprocess
import socket
import struct
import fcntl


def get_mac(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl(s.fileno(),
                       0x8927,
                       struct.pack('256s', bytes(ifname, 'utf-8')[:15]))
    return ''.join('%02x' % b for b in info[18:24])


def get_ip(ifname):
    addr = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        addr = socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', bytes(ifname[:15], 'utf-8'))
            )[20:24])
        if not addr:
            raise OSError
    except OSError:
        # ok, try with subprocess
        addr = subprocess.check_output(['hostname', '-I']).rstrip().decode()

    if addr and addr != '':
        logging.debug(f'get IP on {ifname}: {addr}')
        return addr
    else:
        logging.error('!cannot acquire IP!')
        return '127.0.0.2'


def get_config(fname):
    """ Get default config from file """
    with open(os.path.join(os.getcwd(), fname)) as f:
        try:
            return yaml.load(f, Loader=yaml.BaseLoader)
        except Exception:
            raise


class Event:

    def __init__(self, _type, cmd, data=None):
        self.type = _type
        self.cmd = cmd
        if data:
            self.data = data

            if self.type == 'mqtt':
                self.payload = self.data.get('payload')
                self.server_cmd = self.data.get('command')

    def __repr__(self):
        return '[ EVENT: {} >> {} ]'.format(self.type, self.cmd)


def make_event(_type, cmd, data=None):
    # todo: err handling
    try:
        event = Event(_type, cmd, data)
        return event
    except Exception:
        raise


class FileLock:

    locked = None

    def __init__(self, file_to_lock, timeout=1):
        self.timeout = timeout
        self.lock_path = os.path.abspath(file_to_lock) + '.lock'

    def acquire(self):
        """ """
        idx = 0
        while not self.locked:
            try:
                time.sleep(.1)
                with open(self.lock_path, 'w+') as fl:
                    content = fl.read().strip()
                    print(content)
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