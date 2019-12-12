import time
from threading import Thread
import multiprocessing as mp
from mqtt_client import CDLClient
from handlers.base import MQTTManager
from skabenclient.helpers import get_mac, get_ip


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
              device_handler,
              event_handler,
              **kwargs):

    config.update({
        'uid': get_mac(config['iface']),
        'ip': get_ip(config['iface']),
        'q_int': mp.Queue(),
        'q_ext': mp.Queue(),
        'device_handler': device_handler,
        'event_handler': event_handler
    })

    config.update(**kwargs)

    client = CDLClient(q_ext=config.q_ext,
                       q_int=config.q_int,
                       broker_ip=config.broker_ip,
                       dev_type=config.dev_type,
                       uid=config.uid)

    router = Router(config)

    try:
        client.start()
        router.start()
        config['end_device'].run()
    except Exception:
        raise
    finally:
        router.join(1)
        client.join(1)
        print(f'running config:\n {config}')
