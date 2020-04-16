import time

from threading import Thread
from skabenclient.mqtt_client import MQTTClient
from skabenclient.contexts import MQTTContext, EventContext


class EventRouter(Thread):

    """
        Routing and handling queue events

        external queue used only for sending messages to server via MQTT
        new mqtt messages from server comes to internal queue from MQTTClient
        queues separated because of server messages top priority
    """

    def __init__(self, config, event_context):
        super().__init__()
        self.daemon = True
        self.running = False
        self.q_int = config.get("q_int")
        self.q_ext = config.get("q_ext")
        self.logger = config.logger()
        self.config = config  # for passing to contexts
        self.event_context = event_context

    def run(self):
        """ Routing events from internal queue """
        self.logger.debug('router module starting...')
        self.running = True
        while self.running:
            if self.q_int.empty():
                time.sleep(.1)
                continue
            try:
                # TODO: NAKOORENO
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
                        with self.event_context(self.config) as context:
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


def start_app(app_config,
              device,
              event_context=EventContext):
    """ Start application

        app_config: system skaben config object
        device: end device for user interactions
        event_context: device events controller

    """

    app_config.update({'device': device})  # update config for easy access to device instance
    router = EventRouter(app_config, event_context)  # initialize router for internal events
    mqttc = MQTTClient(app_config)  # initialize MQTT client for talking with server

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
