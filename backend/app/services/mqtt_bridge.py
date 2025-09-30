import json
import threading
import paho.mqtt.client as mqtt


class MQTTBridge:
    """
    Minimal Paho MQTT wrapper for MVP.
    Subscribes to DC telemetry; can publish switch commands.
    """

    def __init__(self, host: str, port: int, base: str, on_dc_measure):
        self.host, self.port = host, port
        self.base = base.rstrip("/")
        self.on_dc_measure = on_dc_measure

        self.client = mqtt.Client(protocol=mqtt.MQTTv311)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        print("MQTT connected, rc=", rc)
        topic = f"{self.base}/telemetry/dc/+/measure"
        print("Subscribing to:", topic)
        client.subscribe(topic)

    def _on_message(self, client, userdata, msg):
        print("MQTT msg:", msg.topic, msg.payload)
        try:
            device_id = msg.topic.split("/")[-2]
            payload = json.loads(msg.payload.decode())
            self.on_dc_measure(device_id, payload)
        except Exception:
            pass

    def start(self):
        self.client.connect(self.host, self.port, keepalive=60)
        threading.Thread(target=self.client.loop_forever, daemon=True).start()

    # publish control commands
    def publish_switch(self, channel_id: str, state: str):
        topic = f"{self.base}/control/switch/{channel_id}/set"
        self.client.publish(topic, state)
