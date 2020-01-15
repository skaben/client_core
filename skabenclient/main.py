import time
from threading import Thread
from skabenclient.mqtt_client import MQTTClient
from skabenclient.contexts import MQTTContext, EventContext


class EventRouter(Thread):

    """
        mr Slim Controller wannabe

        routing internal queue events

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
        self.device = config.get('device')
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
                        # catch exit from end device, stopping app
                        self.q_ext.put(('exit', 'message'))
                        self.stop()
                    else:
                        # passing to event manager
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


def start_app(app_config, device):

    app_config.update({'device': device})  # assign end device for user interactions
    mqttc = MQTTClient(app_config)  # initialize MQTT client for talking with server
    router = EventRouter(app_config)  # initialize router for internal events

    try:
        mqttc.start()
        router.start()
        app_config.get('device').run()
    except Exception:
        raise
    finally:
        router.join(.5)
        mqttc.join(.5)
        print(f'running application with config:\n {app_config}')
