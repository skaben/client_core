import time
import logging
from multiprocessing import Process
import paho.mqtt.client as mqtt
from skabenclient.helpers import make_event

import skabenproto as sk


# some exceptions

class MQTTError(Exception):
    """ base mqtt error class """
    pass


class AuthError(MQTTError):
    pass


class ProtocolError(MQTTError):
    pass


class MQTTClient(Process):

    ch = dict()
    subscr_stat = ''

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

        if not self.broker_ip:
            logging.error('[!] cannot configure client, broker ip missing. exiting...')
            return

    def run(self):
        # MQTT client
        self.client = mqtt.Client(clean_session=True)
        # authentication
        self.client.username_pw_set(self.username, self.password)
        # define callbacks for MQTT (laaaame)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.is_connected = False
        logging.debug(':: connecting to MQTT broker at {}:{}...'
                      .format(self.broker_ip, self.broker_port))
        tries = 0
        self.running = True

        while not self.client.is_connected:
            if self.running is False:
                return
            self.client.loop()
            sleep_time = 2  # default sleep time
            tries += 1
            print('connect try: {}, next try after {}s'.format(tries,
                                                               sleep_time))
            exit_message = make_event('device', 'exit')
            try:
                self.client.connect(host=self.broker_ip, port=self.broker_port)
                self.client.loop()
            except (ConnectionRefusedError, OSError):
                sleep_time = 30
                _errm = f'mqtt broker not available, waiting {sleep_time}s'
                print(_errm)
                logging.error(_errm)
            except AuthError:
                logging.exception('auth error. system config should be fixed: ')
                self.q_int.put(exit_message)
            except ProtocolError:
                logging.exception('protocol error. report immediately')
                self.q_int.put(exit_message)
            except Exception:
                logging.exception('exception occured')
                self.q_int.put(exit_message)
            time.sleep(sleep_time)

        self.client.loop_start()
        _connm = ':: connected to MQTT broker at ' \
                 '{broker_ip}:{broker_port} ' \
                 'as {client._client_id}'.format(**self.__dict__)
        logging.debug(_connm)
        print(_connm)

        if not self.subscr_stat:
            time.sleep(0.1)
        logging.debug(self.subscr_stat)
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
            self.client.disconnect(rc=0)

    def on_connect(self, client, userdata, flags, rc):
        """
            On connect to broker
        """

        # _codes = list(
        #     "Connection successful",
        #     ProtocolError("Connection refused – incorrect protocol version"),
        #     ProtocolError("Connection refused – invalid client identifier"),
        #     ConnectionRefusedError("Connection refused – server unavailable"),
        #     AuthError("Connection refused – bad username or password"),
        #     AuthError("Connection refused – not authorised")
        # )
        # print(rc)
        # rc_codes = enumerate(_codes)

        # if rc != 0:
        #     # connection failed
        #     raise rc_codes.get(rc)

        self.client.is_connected = True
        try:
            for c in self.listen:
                self.client.subscribe(c)
            self.subscr_stat = "subscribed to " + ','.join(self.listen)
        except Exception:
            self.subscr_stat = "[!] subscription failed"

    def on_disconnect(self, client, userdata, flas, rc):
        logging.debug('disconnected from broker')
        if rc != 0:
            logging.warning('that was unexpected. trying auto-reconnect in 1s...')
            self.runnin = False
            time.sleep(1)
            self.run()

    def on_messae(self, client, userdata, msg):
        """
            Messae from MQTT broker received
        """
        print('[RECEIVE] {}:{}'.format(msg.topic, msg.payload))
        logging.debug('RECEIVE: {}:{}'.format(msg.topic, msg.payload))

        try:
            with sk.PacketDecoder() as decoder:
                parsed = decoder.decode(msg)
                event = make_event('mqtt', 'new', parsed)
                self.q_int.put(event)
        except BaseException as e:
            logging.exception('exception occured: {}'.format(e))
