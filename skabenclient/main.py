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
    mqtt_client = None
    standalone = app_config.get("standalone")

    try:
        if not standalone:
            mqtt_client = MQTTClient(app_config)  # initialize MQTT client for talking with server
            mqtt_client.start()
        router.start()
        device.run()
        print(f'running application with config:\n {app_config}')
    except KeyboardInterrupt:
        print('catched keyboard interrupt')
        raise SystemExit('exiting')
    except Exception:
        raise
    finally:
        router.join(.5)
        if mqtt_client:
            mqtt_client.join(.5)
