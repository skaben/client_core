import os
import time
import json
import random
import logging

from threading import Thread

from skabenproto import packets as sp
from skabenclient.helpers import make_event

# TODO: refactor it.


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

        self.timestamp = self.get_last_timestamp()

    def get_last_timestamp(self):
        """ Read previous timestamp value from 'ts' file """
        with open(self.timestamp_fname, 'r') as fh:
            t = fh.read().rstrip()
            if t:
                return int(t)
            else:
                return 0

    def rewrite_timestamp(self, new_ts):
        """ Write timestamp value to file 'ts' """
        with open(self.timestamp_fname, 'w') as fh:
            fh.write(str(int(new_ts)))
            return int(new_ts)

    def __enter__(self):
        return self

    def __exit__(self, *err):
        return


class MQTTParseContext(BaseContext):
    """ MQTT context manager

        parsing mqtt messages, send responses, pass events to device handlers
    """

    def __init__(self, config):
        super().__init__(config)

    def manage(self, event):
        """ Manage event from MQTT
            Command parsing and event routing
        """
        # todo: error handling

        if command == 'WAIT':
            # send me to the future
            self.rewrite_ts(timestamp + datahold['timeout'])
            return

        if timestamp < self.timestamp:
            # ignoring messages from the past
            if command not in ('CUP', 'SUP'):
                return

        # update local ts from event
        self.rewrite_timestamp(timestamp)

        try:
            if command == 'PING':
                # reply with pong immediately
                packet = sp.PONG(topic=self.config['pub'],
                                 uid=self.uid,
                                 timestamp=self.timestamp)
                self.q_ext.put(packet.encode())
            elif command == 'CUP':
                # pass to internal event context
                event = make_event('device', 'update', datahold.get('fields'))
                self.q_int.put(event)
            elif command == 'SUP':
                # pass to internal event context
                event = make_event('device', 'sup', datahold.get('fields'))
                self.q_int.put(event)
            else:
                raise Exception(f"unrecognized command: {command}")
        except Exception:
            raise

    def __repr__(self):
        return '<PacketManager>'


class EventContext(BaseContext):

    filtered_keys = ['id', 'uid']

    def __init__(self, config):
        super().__init__(config)
        self.task_id = ''.join([str(random.randrange(10)) for _ in range(10)])
        self.device = config.get('device')
        # for event context topic is always pub
        self.topic = self.config.get('pub')
        if not self.device:
            raise Exception(f'{self} error: device not provided')

    def manage(self, event):
        """ Managing events based on type """
        # receive update from server

        if event.cmd == 'update':
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

        # request config from server
        elif event.cmd == 'cup':
            return self.config_request(event.data)

        # send current device config to server
        elif event.cmd == 'sup':
            conf = self.get_current_config()
            if event.data:
                conf = [k for k in conf if k in event.data]
            return self.config_send(conf)

        # send data to server directly without local db update
        elif event.cmd == 'info':
            logging.debug('event is {} - sending data to server'.format(event))
            return self.config_send(event.data)

        # input received, update local config, send to server
        elif event.cmd == 'input':
            logging.debug('event is {} - input: {}'.format(event, event.data))
            if event.data:
                self.device.config.save(event.data)
                return self.config_send(event.data)
            else:
                logging.error('missing data from event: {}'.format(event))

        # reload device with current local config
        elif event.cmd == 'reload':
            logging.debug('event is {} - reloading device'.format(event))
            return self.device.state_reload()

        # report bad event type
        else:
            logging.error('bad event {}'.format(event))

    def config_send(self, data=None):
        """ Send config to server """
        if not data:
            logging.error('missing data')
            return
        if not isinstance(data, dict):
            logging.error(f'data is not a dict: {data}')
            return
        data = {k: v for k, v in data.items() if k not in self.filtered_keys}
        # send update to server
        packet = sp.SUP(topic=self.config.get('pub'),
                        uid=self.config.get('uid'),
                        task_id=self.task_id,
                        timestamp=self.timestamp,
                        datahold=data)
        self.q_ext.put(packet.encode())

    def config_request(self, keys=None):
        """ Request config from server """
        current = self.get_current_config()
        if keys:
            datahold = {'request': [k for k in current if k in keys]}
        else:
            datahold = {'request': 'all'}  # full conf

        packet = sp.CUP(topic=self.config.get('pub'),
                        uid=self.config.get('uid'),
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
        packet = packet_class(topic=self.config.get('pub'),
                              timestamp=self.timestamp,
                              uid=self.config.get('uid'),
                              task_id=task_id)
        self.q_ext.put(packet.encode())

    def get_current_config(self):
        """ load current device config """
        current = self.device.config.data
        if not current:
            current = self.device.config.load()
        return current


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
                # get event from internal queue
                event = self.q_int.get()

                # packets with label 'mqtt' comes from server
                if event.type == 'mqtt':
                    # decode and parse it with MQTTParseContext
                    with MQTTParseContext(self.config) as mqtt:
                        mqtt.manage(event)

                # packets with label 'device' comes from self, client
                elif event.type == 'device':
                    # catch exit from end device, stopping client
                    if event.cmd == 'exit':
                        self.q_ext.put(('exit', 'message'))
                        self.stop()
                        break
                    # or normally manage event with main context
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
