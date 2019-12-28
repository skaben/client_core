import time
from threading import Thread
from skabenclient.mqtt_client import CDLClient
from skabenclient.managers import MQTTManager


class Router(Thread):

    """
        mr Slim Controller wannabe
    """

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.q_int = config.q_int
        self.q_ext = config.q_ext
        self.logger = config.logger
        self.handler = config.handler
        self.running = True

    def run(self):
        self.logger.debug('router module starting...')
        while self.running:
            if self.q_int.empty():
                time.sleep(.1)
                continue
            try:
                # TODO: more clear queue system
                msg = self.q_int.get()
                # get packets with label 'mqtt' (from server)
                if msg.type == 'mqtt':
                    # PacketManager will manage events and send replies
                    # 1. directly (in case of ping/pong or wait)
                    # 2. with re-entry to q_int queue with label 'device'
                    with MQTTManager(self.config) as mqtt_manager:
                        mqtt_manager.manage(msg)  # managing event
                elif msg.type == 'device':
                    if msg.cmd == 'exit':
                        # catch exit from end device, stopping app
                        self.q_ext.put(('exit', 'message'))
                        self.running = False
                    else:
                        with self.handler(self.config) as handler:
                            handler.manage(msg)
                else:
                    self.logger.error('cannot determine message type for:\n{}'.format(msg))
            except Exception:
                self.logger.exception('exception in manager context:')
                self.running = False
        self.logger.debug('router module stopping...')

    def stop(self):
        self.running = False


def start_app(config,
              device,
              event_handler,
              **kwargs):

    config.update({
        'device': device,
        'event_handler': event_handler
    })

    config.update(kwargs)
    data = config.data

    client = CDLClient(q_ext=data['q_ext'],
                       q_int=data['q_int'],
                       broker_ip=data['broker_ip'],
                       dev_type=data['dev_type'],
                       uid=data['uid'])

    router = Router(config)

    try:
        client.start()  # MQTT client
        router.start()  # message routing
        config['device'].run()  # device interface
    except Exception:
        raise
    finally:
        router.join(1)
        client.join(1)
        print(f'running config:\n {config}')
