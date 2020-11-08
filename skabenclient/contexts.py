import os
import time
import random
import logging

from threading import Thread

from skabenproto import packets as sp
from skabenclient.helpers import make_event


class BaseContext:
    """
       Context base class
       (separated timestamp management and helper functions)
    """

    event = dict()

    def __init__(self, app_config):
        self.config = app_config

        self.logger = self.config.logger()
        self.q_int = self.config.get('q_int')
        if not self.q_int:
            raise Exception('internal event queue not declared')
        self.q_ext = self.config.get('q_ext')
        if not self.q_ext:
            raise Exception('external (to server) event queue not declared')

        # keepalive TS management
        self.timestamp_fname = os.path.join(self.config.root, 'timestamp')
        if not os.path.exists(self.timestamp_fname):
            with open(self.timestamp_fname, 'w') as fh:
                fh.write('0')

        self.timestamp = self.get_last_timestamp()
        self.task_id = ''.join([str(random.randrange(10)) for _ in range(10)])

        # for event context topic is always pub
        self.topic = self.config.get('pub')
        self.uid = self.config.get('uid')
        self.device = self.config.get("device")
        if not self.device:
            raise Exception(f'{self} error: device not provided')

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

    def get_current_config(self):
        """ load current device config """
        current = self.device.config.data
        if not current:
            current = self.device.config.load()
        return current

    def confirm_update(self, task_id, packet_type='ACK'):
        """ ACK/NACK packet """
        if packet_type not in ('ACK', 'NACK'):
            raise Exception(f'packet type not ACK or NACK: {packet_type}')

        packet_class = getattr(sp, packet_type)
        packet = packet_class(topic=self.config.get('pub'),
                              timestamp=self.timestamp,
                              uid=self.config.get('uid'),
                              task_id=task_id)
        self.q_ext.put(packet.encode())

    def __enter__(self):
        return self

    def __exit__(self, *err):
        return


class EventContext(BaseContext):

    filtered_keys = ['id', 'uid']

    def absorb(self, event):
        try:
            if event.type == "mqtt":
                self.manage_mqtt(event)
            elif event.type == 'device':
                self.manage(event)
        except Exception:
            # TODO: send message to q_ext on fail
            raise

    def send_task_response(self, event):
        task_id = event.data.get('task_id', '12345')
        response = 'ACK'
        try:
            self.device.config.save(event.data)
        except Exception:
            response = 'NACK'
            logging.exception('cannot apply new config')
        finally:
            return self.confirm_update(task_id, response)

    def manage(self, event):
        """ Managing events based on type """
        # receive update from server
        command = event.cmd.lower()

        # update from server received, save to local config
        if command == 'update':
            return self.save_config_and_report(event)

        # request config from server
        elif command == 'cup':
            return self.send_config_request(event.data)

        # send current device config to server
        elif command == 'sup':
            conf = self.get_current_config()
            # send only required fields
            if event.data:
                filtered = {k:v for k,v in conf.items() if k in event.data}
                if filtered:
                    conf = filtered
            return self.send_config(conf)

        # send data to server directly without local db update
        elif command == 'info':
            logging.debug('event is {} - sending data to server'.format(event))
            return self.send_message(event.data)

        # input received, update local config, send to server
        elif command == 'input':
            logging.debug('input event is {} - input: {}'.format(event, event.data))
            if event.data:
                self.device.config.save(event.data)
                return self.send_config(event.data)
            else:
                logging.error('missing data from event: {}'.format(event))

        # reload device with current local config
        elif command in ('reload', 'reset'):
            logging.debug('event is {} - reloading device'.format(event))
            return self.device.state_reload()

        # report bad event type
        else:
            logging.error('bad event {}'.format(event))

    def manage_mqtt(self, event):
        """ Manage event from MQTT based on command
            Translate commands into internal event queue
        """

        command = event.data.get('command')
        timestamp = event.data.get('timestamp')
        datahold = event.data.get('datahold')

        if command == 'WAIT':
            # send me to the future
            self.rewrite_timestamp(timestamp + datahold['timeout'])
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
                packet = sp.PONG(topic=self.topic,
                                 uid=self.uid,
                                 timestamp=self.timestamp)
                self.q_ext.put(packet.encode())
            elif command == 'CUP':
                # update local configuration from packet data
                event = make_event('device', 'update', datahold)
                self.q_int.put(event)
            elif command == 'SUP':
                # send local configuration to server (filtered by field list)
                event = make_event('device', 'sup', datahold.get('fields'))
                self.q_int.put(event)
            else:
                raise Exception(f"unrecognized command: {command}")
        except Exception:
            raise

    def send_message(self, data):
        """ INFO packet """
        packet = sp.INFO(topic=self.topic,
                         uid=self.uid,
                         timestamp=self.timestamp,
                         datahold=data)
        self.q_ext.put(packet.encode())

    def send_config(self, data=None):
        """ SUP packet """
        try:
            if not data:
                raise Exception("empty data")
            if not isinstance(data, dict):
                raise Exception(f'data is not a dict: {data}')

            data = {k: v for k, v in data.items() if k not in self.filtered_keys}
            # send update to server
            packet = sp.SUP(topic=self.topic,
                            uid=self.uid,
                            task_id=self.task_id,
                            timestamp=self.timestamp,
                            datahold=data)
            self.q_ext.put(packet.encode())
        except Exception as e:
            logging.exception(f"error in context config send - {e} \n {self}")

    def send_config_request(self, keys=None):
        """ CUP packet """
        current = self.get_current_config()
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

    def save_config_and_report(self, event):
        """ ACK/NACK packet """
        task_id = event.data.get('task_id', '12345')
        response = 'ACK'
        try:
            self.device.config.save(event.data)
        except Exception:
            response = 'NACK'
            logging.exception('cannot apply new config')
        finally:
            return self.confirm_update(task_id, response)


class Router(Thread):

    """
        Routing and handling queue events

        external queue used only for sending messages to server via MQTT
        new mqtt messages from server comes to internal queue from MQTTClient
        queues separated because of server messages top priority
    """

    managed_events = ["exit", "device", "mqtt"]

    def __init__(self, config):
        super().__init__()
        self.daemon = True
        self.running = False
        self.q_int = config.get("q_int")
        self.q_ext = config.get("q_ext")
        self.logger = config.logger()
        # passing to contexts
        self.config = config

    def run(self):
        """ Routing events from internal queue """
        self.logger.debug('router module starting...')
        self.running = True

        while self.running:
            if self.q_int.empty():
                time.sleep(.1)
                continue

            # get event from internal queue
            try:
                event = self.q_int.get()

                if event.type not in self.managed_events:
                    raise Exception('cannot determine message type for:\n{}'.format(event))
                elif event.type == "exit":
                    self.q_ext.put(event)
                    return self.stop()

                with EventContext(self.config) as context:
                    context.absorb(event)

            except Exception:
                self.logger.exception('exception in manager context:')
                self.stop()

    def stop(self):
        """ Full stop """
        self.logger.debug('router module stopping...')
        self.running = False
