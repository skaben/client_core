from skabenclient.config import SystemConfig
from skabenclient.contexts import Router
from skabenclient.device import BaseDevice
from skabenclient.mqtt_client import MQTTClient


def start_app(app_config: SystemConfig, device: BaseDevice):
    """ Start application

        app_config: system skaben config object
        device: end device for user interactions
        event_context: device events controller

    """

    app_config.update({'device': device})  # update config for easy access to device instance
    router = Router(app_config)  # initialize router for internal events
    mqtt_client = None
    standalone = app_config.get("standalone")

    try:
        if not standalone:
            mqtt_client = MQTTClient(app_config)  # initialize MQTT client for talking with server
            mqtt_client.start()
        router.start()
        device.run()
    except KeyboardInterrupt:
        raise SystemExit('Catch keyboard interrupt. Exiting')
    except Exception:
        raise
    finally:
        router.join(.5)
        if mqtt_client:
            mqtt_client.join(.5)
