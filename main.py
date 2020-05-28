from skabenclient.mqtt_client import MQTTClient
from skabenclient.contexts import Router


def start_app(app_config, device):
    """ Start application

        app_config: system skaben config object
        device: end device for user interactions
        event_context: device events controller

    """

    app_config.update({'device': device})  # update config for easy access to device instance
    router = Router(app_config)  # initialize router for internal events
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
