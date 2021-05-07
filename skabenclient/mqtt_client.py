import json
import time

from typing import Any
from multiprocessing import Process
import paho.mqtt.client as mqtt

from skabenclient.helpers import make_event
from skabenclient.config import SystemConfig


class MQTTError(Exception):
    """Exception raised for errors in the mqtt

    Attributes:
        expression -- input expression in which the error occurred
        message -- explanation of the error
    """

    def __init__(self, message: str):
        self.message = message


class MQTTAuthError(MQTTError):
    def __init__(self, message: str):
        super().__init__(message)


class MQTTProtocolError(MQTTError):
    def __init__(self, message: str):
        super().__init__(message)


# NB: not working at all
auth_exc = {
    "0": "Connection successful",
    "1": MQTTProtocolError("Connection refused – incorrect protocol version"),
    "2": MQTTProtocolError("Connection refused – invalid client identifier"),
    "3": ConnectionRefusedError("Connection refused – server unavailable"),
    "4": MQTTAuthError("Connection refused – bad username or password"),
    "5": MQTTAuthError("Connection refused – not authorised")
}


class MQTTClient(Process):

    ch = dict()
    subscriptions_info = ''
    default_timeout = 2
    running = None

    def __init__(self, config: SystemConfig):
        super().__init__()

        self.event = dict()
        self.daemon = True
        self.client = None
        self.logger = config.logger()

        # Queues
        self.q_int = config.get('q_int')
        self.q_ext = config.get('q_ext')

        # Device
        self.skip_until = 0
        self.pub = config.get('pub')
        self.sub = config.get('sub')

        # MQTT broker
        self.broker_ip = config.get('broker_ip')
        self.broker_port = config.get('broker_port', 1883)
        self.username = config.get('username')
        self.password = config.get('password')
        self.client_id = f"{config.get('topic')}_{config.get('uid')}"

        if not self.broker_ip:
            self.logger.error('[!] cannot configure client, broker ip missing. exiting...')
            return

    def init_client(self):
        # MQTT client
        client = mqtt.Client(clean_session=True)
        # authentication
        client.username_pw_set(self.username, self.password)
        # define callbacks for MQTT (laaaame)
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.on_disconnect = self.on_disconnect
        client._client_id = self.client_id
        self.is_connected = False
        return client

    def connect_client(self):
        tries = 0
        while not self.is_connected:
            if self.running is False:
                return
            self.client.loop()  # manual loop while not connected
            sleep_time = self.default_timeout  # default sleep time
            tries += 1
            self.logger.info(f':: trying MQTT broker: {tries}, next try after {sleep_time}s')
            try:
                self.client.connect(host=self.broker_ip,
                                    port=self.broker_port,
                                    keepalive=60)
            except ValueError:
                _errm = f"check system config, client misconfigured.\n"\
                        f"broker_ip: {self.broker_ip} broker_port: {self.broker_port}"
                self.client.loop_stop()
                self.stop()
            except (ConnectionRefusedError, OSError):
                sleep_time = 30
                _errm = f'mqtt broker not available, waiting {sleep_time}s'
                self.logger.error(_errm)
            except MQTTAuthError:
                self.logger.exception('auth error. check system config ')
                self.stop()
            except MQTTProtocolError:
                self.logger.exception('protocol error. report immediately')
                self.stop()
            except Exception:
                self.logger.exception('exception occured')
            time.sleep(sleep_time)

        _connm = ':: connected to MQTT broker at ' \
                 '{broker_ip}:{broker_port} ' \
                 'as {client._client_id}'.format(**self.__dict__)

        self.logger.info(_connm)
        self.client.loop_start()

    def run(self):
        self.logger.debug(f':: connecting to MQTT broker at {self.broker_ip}:{self.broker_port}')
        self.running = True

        self.client = self.init_client()
        self.connect_client()
        # all seems legit, running loop in separated thread

        try:
            self.logger.debug('MQTT module starting')
            while self.running:
                if self.q_ext.empty():
                    time.sleep(.1)
                else:
                    message = self.q_ext.get()
                    if message[0] == 'exit':
                        self.logger.info('mqtt module stopping...')
                        self.running = False
                    elif message[0] == 'reconnect':
                        self.reconnect(message[1])
                    else:
                        self.logger.debug(f'[SENDING] {message}')
                        if isinstance(message, tuple):
                            self.client.publish(*message)
                        else:
                            self.logger.debug(f'bad message to publish: {message}')
        except Exception:
            self.logger.exception('catch error in mqtt module: ')
        finally:
            self.client.disconnect(self.client, 0)

    def stop(self):
        exit_message = make_event('exit', 'exit')
        self.q_int.put(exit_message)
        self.running = False

    def reconnect(self, rc: int):
        try:
            self.logger.warning(f'unexpected disconnect (code {rc}).\ntrying auto-reconnect...')
            self.is_connected = False
            self.client.loop_stop()
            time.sleep(self.default_timeout)
            # don't want to mess with paho reconnection routines, just recreate the client
            self.client = self.init_client()
            result = self.connect_client()
            self.logger.info(result)
            # all seems legit, running loop in separated thread
            self.client.loop_start()
        except Exception:
            raise

    def on_connect(self, client: mqtt.Client, userdata: Any, flags, rc: int):
        """On connect to broker
            TODO: type annotation for userdata
        """

        if 6 > rc > 0:
            # connection failed
            raise auth_exc.get(str(rc))

        self.is_connected = True

        try:
            for c in self.sub:
                self.client.subscribe(c)
            self.subscriptions_info = "subscribed to " + ','.join(self.sub)
        except Exception:
            raise

        # request config on connect
        request_config_event = make_event("device", "cup")
        self.q_int.put(request_config_event)

    def on_disconnect(self, client: mqtt.Client, userdata, rc):
        """On disconnect from broker
            TODO: type annotation for userdata
        """
        self.logger.info('disconnected from broker')
        rc = int(rc)
        if rc != 0:
            self.q_ext.put(('reconnect', rc))
        else:
            self.running = False
            self.client.loop_stop(force=True)

    def on_message(self, client: mqtt.Client, userdata, msg):
        """Message from MQTT broker received
           receive message as (str, b'{}'), return dict
           TODO: type annotations for userdata, msg
        """
        self.logger.debug(f'RECEIVE: {msg.topic} {msg.payload}')

        try:
            full_topic = msg.topic.split('/')
            if 2 > len(full_topic) > 3:
                raise Exception(f'unsupported topic format: {full_topic}')
            payload = json.loads(msg.payload.decode('utf-8'))

            data = dict(topic=full_topic[0],
                        uid=full_topic[1] if len(full_topic) == 3 else None,
                        command=full_topic[-1],
                        task_id=payload.get('task_id'),
                        timestamp=int(payload.get('timestamp')),
                        datahold=payload.get('datahold'))
            event = make_event('mqtt', 'new', data)
            self.q_int.put(event)
        except BaseException:
            self.logger.exception('while receiving message')
