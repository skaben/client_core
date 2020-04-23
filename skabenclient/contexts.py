import os
import time
import random
import logging

from threading import Thread

from skabenproto import packets as sp
from skabenclient.helpers import make_event


class BaseContext:
    """
       Basic context manager abstract class
    """

    event = dict()

    def __init__(self, config):
        self.config = config
        self.logger = config.logger()

        self.q_int = self.config.get('q_int')
        if not self.q_int:
            raise Exception('internal event queue not declared')

        self.q_ext = self.config.get('q_ext')
        if not self.q_ext:
            raise Exception('external (to server) event queue not declared')

        # keepalive TS management
        self.timestamp_fname = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ts')
        if not os.path.exists(self.timestamp_fname):
            with open(self.timestamp_fname, 'w') as fh:
                fh.write('0')

        self.timestamp = self._last_ts()
        self.topic = config.get('topic')
        self.uid = config.get('uid')

        if not self.topic:
            raise Exception('improperly configured - system config missing topic')

    def _last_ts(self):
        """ Read previous timestamp value from 'ts' file """
        with open(self.timestamp_fname, 'r') as fh:
            t = fh.read().rstrip()
            if t:
                return int(t)
            else:
                return 0

    def rewrite_ts(self, new_ts):
        """ Write timestamp value to file 'ts' """
        with open(self.timestamp_fname, 'w') as fh:
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
        event_ts = int(event.datahold.get('ts', '-1'))

        if event.server_cmd == 'WAIT':
            # push me to the future
            self.rewrite_ts(event_ts + event.datahold['timeout'])
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
        packet = sp.PONG(topic=self.topic,
                         uid=self.uid,
                         timestamp=self.timestamp)
        self.q_ext.put(packet.encode())

    def wait(self):
        """ Waiting for timeout """
        to = self.event.datahold.get('timeout', 0)\
            + self.event.datahold.get('ts')
        self.skip_until = to

    def local_update(self):
        """ Updating local device state from MQTT event
            Event should be handled by device handler respectively
        """
        event = make_event('device', 'update', self.event.datahold)
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
        """ Managing events based on type """
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
        if not data:
            logging.error('missing data')
            return
        if not isinstance(data, dict):
            logging.error(f'data is not a dict: {data}')
            return
        data = {k: v for k, v in data.items() if k not in self.filtered_keys}
        # send update to server DB
        packet = sp.SUP(topic=self.topic,
                        uid=self.uid,
                        task_id=self.task_id,
                        timestamp=self.timestamp,
                        datahold=data)
        self.q_ext.put(packet.encode())

    def config_reply(self, keys=None):
        current = self.device.config.data
        if not current:
            current = self.device.config.load()
        if keys:
            datahold = {'request': [k for k in current if k in keys]}
        else:
            datahold = {'request': 'all'}  # full conf

        packet = sp.CUP(topic=self.topic,
                        uid=self.uid,
                        timestamp=self.timestamp,
                        task_id=self.task_id,
                        datahold=datahold)
        self.q_ext.put(packet.encode())

    def confirm_update(self, task_id, packet_type='ACK'):
        """ Confirm to server that we received and applied config
            should be initialized only after device handler success
        """
        if packet_type not in ('ACK', 'NACK'):
            raise Exception(f'packet type not ACK or NACK: {packet_type}')

        packet_class = getattr(sp, packet_type)
        packet = packet_class(topic=self.topic,
                              timestamp=self.timestamp,
                              uid=self.uid,
                              task_id=task_id)
        self.q_ext.put(packet.encode())


class Router(Thread):

    """
        Routing and handling queue events

        external queue used only for sending messages to server via MQTT
        new mqtt messages from server comes to internal queue from MQTTClient
        queues separated because of server messages top priority
    """

    def __init__(self, config):
        super().__init__()
        self.daemon = True
        self.running = False
        self.q_int = config.get("q_int")
        self.q_ext = config.get("q_ext")
        self.logger = config.logger()
        self.config = config  # for passing to contexts

    def run(self):
        """ Routing events from internal queue """
        self.logger.debug('router module starting...')
        self.running = True
        while self.running:
            if self.q_int.empty():
                time.sleep(.1)
                continue
            try:
                event = self.q_int.get()
                if event.type == 'mqtt':
                    # get packets with label 'mqtt' (from server)
                    with MQTTContext(self.config) as mqtt:
                        mqtt.manage(event)
                elif event.type == 'device':
                    if event.cmd == 'exit':
                        # catch exit from end device, stopping skaben
                        self.q_ext.put(('exit', 'message'))
                        self.stop()
                    else:
                        # passing to event context manager
                        with EventContext(self.config) as context:
                            context.manage(event)
                else:
                    self.logger.error('cannot determine message type for:\n{}'.format(event))
            except Exception:
                self.logger.exception('exception in manager context:')
                self.stop()

    def stop(self):
        """ Full stop """
        self.logger.debug('router module stopping...')
        self.running = False
