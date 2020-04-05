import os
import random
import logging
import netifaces as netif

import skabenproto as sk
from skabenclient.helpers import make_event


class BaseContext:
    """
       Basic context manager abstract class
    """

    event = dict()

    def __init__(self, config):
        self.sys_conf = config.data
        self.logger = config.logger()
        self.q_int = self.sys_conf.get('q_int')
        if not self.q_int:
            raise Exception('internal queue not declared')
        self.q_ext = self.sys_conf.get('q_ext')
        if not self.q_ext:
            raise Exception('external (to mqtt) queue not declared')
        # keepalive TS management
        self.ts_fname = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ts')
        if not os.path.exists(self.ts_fname):
            with open(self.ts_fname, 'w') as fh:
                fh.write('0')
        self.ts = self._last_ts()
        self.dev_type = self.sys_conf.get('dev_type')
        self.uid = self.sys_conf.get('uid')
        self.reply_channel = self.dev_type + 'ask'

    def get_ip_addr(self):
        """ Get IP address by interface name """
        try:
            iface = self.sys_conf.get('iface')
            self.ip = netif.ifaddresses(iface)[netif.AF_INET][0]['addr']
            return self.ip
        except Exception:
            raise

    def _last_ts(self):
        """ Read previous timestamp value from 'ts' file """
        with open(self.ts_fname, 'r') as fh:
            t = fh.read().rstrip()
            if t:
                return int(t)
            else:
                return 0

    def rewrite_ts(self, new_ts):
        """ Write timestamp value to file 'ts' """
        with open(self.ts_fname, 'w') as fh:
            fh.write(str(int(new_ts)))
            return int(new_ts)

    def __enter__(self):
        return self

    def __exit__(self, *err):
        return


class MQTTContext(BaseContext):
    """ MQTT context manager

        parsing mqtt messages, send responses, pass events to device handlers
    """

    def __init__(self, config):
        super().__init__(config)

        # command table
        self.reactions = {
            "PING": self.pong,
            "WAIT": self.wait,
            "CUP": self.local_update,
            "SUP": self.local_send
        }

    def manage(self, event):
        """ Manage event from MQTT
            Command parsing and event routing
        """
        self.event = event

        my_ts = self._last_ts()
        event_ts = int(event.payload.get('ts', '-1'))

        if event.server_cmd == 'WAIT':
            # push me to the future
            self.rewrite_ts(event_ts + event.payload['timeout'])
            return

        if event_ts < my_ts:
            # ignoring messages from the past
            if event.server_cmd not in ('CUP', 'SUP'):
                return

        # update local ts from event
        self.rewrite_ts(event_ts)

        try:
            return self.reactions[self.event.server_cmd]()
        except KeyError:
            raise Exception('unrecognized command: {}'
                            .format(self.event.data.get("command")))

    def pong(self):
        """ Send PONG packet via MQTT """
        with sk.PacketEncoder() as p:
            packet = p.load('PONG',
                            dev_type=self.reply_channel,
                            uid=self.uid)
            encoded = p.encode(packet, self.ts)
            self.q_ext.put(encoded)

    def wait(self):
        """ Waiting for timeout """
        to = self.event.payload.get('timeout', 0)\
            + self.event.payload.get('ts')
        self.skip_until = to

    def local_update(self):
        """ Updating local device state from MQTT event
            Event should be handled by device handler respectively
        """
        event = make_event('device', 'update', self.event.payload)
        self.q_int.put(event)

    def local_send(self, fields=None):
        """ Send local config via MQTT """
        event = make_event('device', 'send', fields)
        self.q_int.put(event)

    def __repr__(self):
        return '<PacketManager>'


class EventContext(BaseContext):

    filtered_keys = ['id', 'uid']

    def __init__(self, config):
        super().__init__(config)
        self.task_id = ''.join([str(random.randrange(10)) for _ in range(10)])
        self.device = config.get('device')
        if not self.device:
            raise Exception(f'{self} error: device not provided')

    def manage(self, event):
        if event.cmd == 'update':
            # receive update from server
            logging.debug('event is {} WITH DATA {}'.format(event, event.data))
            task_id = event.data.get('task_id', '12345')
            response = 'ACK'
            try:
                self.device.config.save(event.data)
            except Exception:
                response = 'NACK'
                logging.exception('cannot apply new config')
            finally:
                return self.confirm_update(task_id, response)
        elif event.cmd == 'send':
            # send to server without local db update
            logging.debug('event is {} - sending data to server'.format(event))
            return self.send_config(event.data)
        elif event.cmd == 'input':
            # update local db, send to server
            logging.debug('event is {} - input: {}'.format(event, event.data))
            if event.data:
                self.device.config.save(event.data)
                return self.send_config(event.data)
            else:
                logging.error('missing data from event: {}'.format(event))
        elif event.cmd == 'reload':
            # just reload device with saved plot
            logging.debug('event is {} - reloading device'.format(event))
            return self.device.state_reload()
        else:
            logging.error('bad event {}'.format(event))

    def send_config(self, data):
        """ Send config to server """
        if not data or not isinstance(data, dict):
            logging.error('missing data to send')
            return
        data = {k: v for k, v in data.items() if k not in self.filtered_keys}
        # send update to server DB
        with sk.PacketEncoder() as p:
            packet = p.load('SUP',
                            uid=self.uid,
                            dev_type=self.reply_channel,
                            task_id=self.task_id,
                            payload=data)
            # add IP as additional field
            # packet.payload.update({'ip': self.config['ip']})
            encoded = p.encode(packet, self.ts)
            self.q_ext.put(encoded)

    def config_reply(self, keys=None):
        current = self.device.config.get_current()
        if not current:
            current = self.device.config.load()
        if keys:
            payload = {'request': [k for k in current if k in keys]}
        else:
            payload = {'request': 'all'}  # full conf

        with sk.PacketEncoder() as p:
            packet = p.load('CUP',
                            dev_type=self.reply_channel,
                            uid=self.uid,
                            task_id=self.task_id,
                            payload=payload)
            encoded = p.encode(packet, self.ts)
            self.q_ext.put(encoded)

    def confirm_update(self, task_id, packet_type='ACK'):
        """ Confirm to server that we received and applied config
            should be initialized only after device handler success
        """
        if packet_type not in ('ACK', 'NACK'):
            raise Exception(f'packet type not ACK or NACK: {packet_type}')

        with sk.PacketEncoder() as p:
            packet = p.load(packet_type,
                            dev_type=self.reply_channel,
                            uid=self.uid,
                            task_id=task_id)
            encoded = p.encode(packet, self.ts)
            self.q_ext.put(encoded)

#    def send_config_internal(self, msg):
#        """ Deprecated because of class merge """
#        event = make_event('device', 'send', msg)
#        self.q_int.put(event)
#        return f'sending message: {msg}'
