import json
import time
import logging
from multiprocessing import Process
import paho.mqtt.client as mqtt
from skabenclient.helpers import make_event


class MQTTError(Exception):
    """Exception raised for errors in the mqtt

    Attributes:
        expression -- input expression in which the error occurred
        message -- explanation of the error
    """

    def __init__(self, message):
        self.message = message


class MQTTAuthError(MQTTError):
    def __init__(self, message):
        super().__init__(message)


class MQTTProtocolError(MQTTError):
    def __init__(self, message):
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

    def __init__(self, config):
        super().__init__()

        self.event = dict()
        self.daemon = True
        self.client = None

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
            logging.error('[!] cannot configure client, broker ip missing. exiting...')
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
        exit_message = make_event('device', 'exit')
        tries = 0
        while not self.is_connected:
            if self.running is False:
                return
            self.client.loop()  # manual loop while not connected
            sleep_time = self.default_timeout  # default sleep time
            tries += 1
            print(f':: trying MQTT broker: {tries}, next try after {sleep_time}s')
            try:
                self.client.connect(host=self.broker_ip,
                                    port=self.broker_port,
                                    keepalive=60)
            except ValueError:
                _errm = f"check system config, client misconfigured.\n"\
                        f"broker_ip: {self.broker_ip} broker_port: {self.broker_port}"
                self.client.loop_stop()
                self.q_int.put(exit_message)
            except (ConnectionRefusedError, OSError):
                sleep_time = 30
                _errm = f'mqtt broker not available, waiting {sleep_time}s'
                print(_errm)
                logging.error(_errm)
            except MQTTAuthError:
                logging.exception('auth error. check system config ')
                self.q_int.put(exit_message)
            except MQTTProtocolError:
                logging.exception('protocol error. report immediately')
                self.q_int.put(exit_message)
            except Exception:
                logging.exception('exception occured')
                self.q_int.put(exit_message)
            time.sleep(sleep_time)

        _connm = ':: connected to MQTT broker at ' \
                 '{broker_ip}:{broker_port} ' \
                 'as {client._client_id}'.format(**self.__dict__)

        logging.info(_connm)
        print(_connm)
        self.client.loop_start()

    def run(self):
        logging.debug(':: connecting to MQTT broker at {}:{}...'
                      .format(self.broker_ip, self.broker_port))
        self.running = True

        self.client = self.init_client()
        self.connect_client()
        # all seems legit, running loop in separated thread

        try:
            logging.debug('MQTT module starting')
            while self.running:
                if self.q_ext.empty():
                    time.sleep(.1)
                else:
                    message = self.q_ext.get()
                    if message[0] == 'exit':
                        logging.info('mqtt module stopping...')
                        self.running = False
                    elif message[0] == 'reconnect':
                        self.reconnect(message[1])
                    else:
                        logging.debug('[SENDING] {}'.format(message))
                        if isinstance(message, tuple):
                            self.client.publish(*message)
                        else:
                            logging.debug('bad message to publish: {}'
                                          .format(message))
        except Exception:
            logging.exception('catch error in mqtt module: ')
        finally:
            self.client.disconnect(self.client, 0)

    def reconnect(self, rc):
        try:
            logging.warning(f'unexpected disconnect (code {rc}).\ntrying auto-reconnect...')
            self.is_connected = False
            self.client.loop_stop()
            time.sleep(self.default_timeout)
            # don't want to mess with paho reconnection routines, just recreate the client
            self.client = self.init_client()
            result = self.connect_client()
            logging.info(result)
            # all seems legit, running loop in separated thread
            self.client.loop_start()
        except Exception:
            raise

    def on_connect(self, client, userdata, flags, rc):
        """
            On connect to broker
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

    def on_disconnect(self, client, userdata, rc):
        logging.info('disconnected from broker')
        rc = int(rc)
        if rc != 0:
            self.q_ext.put(('reconnect', rc))
        else:
            self.running = False
            self.client.loop_stop(force=True)

    def on_message(self, client, userdata, msg):
        """
            Message from MQTT broker received

            receive message as (str, b'{}'), return dict
        """
        print('[RECEIVE] {}:{}'.format(msg.topic, msg.payload))
        logging.debug('RECEIVE: {}:{}'.format(msg.topic, msg.payload))

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
        except BaseException as e:
            logging.exception('exception occured: {}'.format(e))
