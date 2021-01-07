import os
import time
import random

from threading import Thread
from typing import Union

from skabenproto import packets as sp
from skabenclient.helpers import make_event, Event
from skabenclient.config import SystemConfig


class BaseContext:
    """
       Context base class
       (separated timestamp management and helper functions)
    """

    event = dict()

    def __init__(self, app_config: SystemConfig):
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
        self.device = self.config.get('device')
        if not self.device:
            raise Exception(f'{self} error: device not provided')

    def get_last_timestamp(self):
        """Read previous timestamp value from timestamp file"""
        with open(self.timestamp_fname, 'r') as fh:
            t = fh.read().rstrip()
            try:
                return int(t)
            except Exception:
                t = 0
                self.rewrite_timestamp(t)
                return t

    def rewrite_timestamp(self, new_ts: Union[str, int]) -> int:
        """Write timestamp value to file"""
        with open(self.timestamp_fname, 'w') as fh:
            fh.write(str(int(new_ts)))
            return int(new_ts)

    def get_current_config(self):
        """load current device config
           TODO: check usage of this method! YAGNI
        """

        current = self.device.state
        if not current:
            current = self.device.load()
        return current

    def confirm_update(self, task_id: str, packet_type: str = 'ACK') -> Union[sp.ACK, sp.NACK]:
        """ACK/NACK packet"""
        if packet_type not in ('ACK', 'NACK'):
            raise Exception(f'packet type not ACK or NACK: {packet_type}')

        packet_class = getattr(sp, packet_type)
        packet = packet_class(topic=self.config.get('pub'),
                              timestamp=self.timestamp,
                              uid=self.config.get('uid'),
                              task_id=task_id)
        self.q_ext.put(packet.encode())
        return packet

    def __enter__(self):
        return self

    def __exit__(self, *err):
        return


class EventContext(BaseContext):

    filtered_keys = ['id', 'uid']

    def absorb(self, event: Event):
        try:
            if event.type == "mqtt":
                self.manage_mqtt(event)
            elif event.type == 'device':
                self.manage(event)
        except Exception:
            # TODO: send message to q_ext on fail
            raise

    def manage(self, event: Event):
        """Managing events based on type"""
        try:
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
                    filtered = {k: v for k, v in conf.items() if k in event.data}
                    if filtered:
                        conf = filtered
                return self.send_config(conf)

            # send data to server directly without local db update
            elif command == 'info':
                self.logger.debug(f'sending {event.data} to server')
                return self.send_message(event.data)

            # input received, update local config, send to server
            elif command == 'input':
                self.logger.debug(f'new input: {event.data}')
                if event.data:
                    self.device.save(event.data)
                    return self.send_config(event.data)
                else:
                    self.logger.error(f'missing data from event: {event}')

            # reload device with current local config
            elif command in ('reload', 'reset'):
                self.logger.debug('RESET event, reloading device')
                return self.device.state_reload()

            else:
                self.logger.error(f'bad event {event}')
        except Exception as e:
            raise Exception(f'[E] MAIN context: {e}')

    def manage_mqtt(self, event: Event):
        """Manage event from MQTT based on command
           Translate commands into internal event queue
        """

        command = event.data.get('command', '')
        timestamp = event.data.get('timestamp', 0)
        datahold = event.data.get('datahold', {})

        if command == 'WAIT':
            # send me to the future
            self.rewrite_timestamp(timestamp + datahold.get('timeout', 10))
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
                self.mqtt_to_internal(event, 'update')
            elif command == 'SUP':
                self.mqtt_to_internal(event, 'sup')
            elif command == 'INFO':
                self.mqtt_to_internal(event, 'info')
            else:
                raise Exception(f"unrecognized command: {command}")
        except Exception as e:
            raise Exception(f"[E] MQTT context: {e}")

    def mqtt_to_internal(self, mqtt_event: Event, internal_command: str):
        datahold = mqtt_event.data.get('datahold')
        if not datahold:
            raise Exception(f'empty datahold in {mqtt_event.data.get("command").upper()} packet: {mqtt_event}')
        event = make_event('device', internal_command, datahold)
        self.q_int.put(event)

    def send_message(self, data: dict):
        """INFO packet"""
        packet = sp.INFO(topic=self.topic,
                         uid=self.uid,
                         timestamp=self.timestamp,
                         datahold=data)
        self.q_ext.put(packet.encode())

    def send_config(self, data: dict = None):
        """SUP packet"""
        try:
            if not data:
                raise Exception("cannot send empty data")
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
            raise Exception(f"[E] config send - {e} \n {self}")

    def send_config_request(self, keys: list = None):
        """CUP packet"""
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

    def save_config_and_report(self, event: Event):
        """ACK/NACK packet"""
        # todo: add reason field to ACK/NACK
        response = "ACK"

        try:
            task_id = event.data.get("task_id", "missing")
        except AttributeError as e:
            raise AttributeError(f"nothing to save - datahold missing: {e}")

        try:
            self.device.save(event.data)
            return self.confirm_update(task_id, response)
        except Exception as e:
            response = 'NACK'
            self.logger.exception(f'cannot apply new config: {e}')
            return self.confirm_update(task_id, response)


class Router(Thread):

    """Routing and handling queue events

       external queue used only for sending messages to server via MQTT
       new mqtt messages from server comes to internal queue from MQTTClient
       queues separated because of server messages top priority
    """

    managed_events = ["exit", "device", "mqtt"]

    def __init__(self, config: SystemConfig):
        super().__init__()
        self.daemon = True
        self.running = False
        self.queue_int = config.get("q_int")
        self.queue_ext = config.get("q_ext")
        self.queue_log = config.get("q_log")
        self.logger = config.logger_instance
        # passing to contexts
        self.config = config

    def run(self):
        """Routing events from internal queue"""
        self.logger.debug('router module starting...')
        self.running = True

        while self.running:
            if not self.queue_log.empty():
                log_record = self.queue_log.get()
                self.logger.handle(log_record)

            if self.queue_int.empty():
                time.sleep(.1)
                continue

            # get event from internal queue
            try:
                event = self.queue_int.get()

                if event.type not in self.managed_events:
                    raise Exception(f"cannot determine message type for:\n{event}")
                elif event.type == "exit":
                    self.queue_ext.put(event)
                    return self.stop()

                with EventContext(self.config) as context:
                    context.absorb(event)

            except Exception as e:
                print(f"{e}")
                self.logger.exception("[!]")

    def stop(self):
        """Full stop"""
        self.logger.debug('router module stopping...')
        self.running = False
