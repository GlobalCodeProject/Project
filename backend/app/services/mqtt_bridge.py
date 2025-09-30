import json
import threading
import paho.mqtt.client as mqtt


class MQTTBridge:
    """
    Subscribes to DC and AC telemetry; can publish switch commands.
    """

    def __init__(self, host: str, port: int, base: str,
                 on_dc_measure=None, on_ac_measure=None):
        self.host, self.port = host, port
        self.base = base.rstrip("/")
        self.on_dc_measure = on_dc_measure
        self.on_ac_measure = on_ac_measure

        self.client = mqtt.Client(protocol=mqtt.MQTTv311)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        dc_topic = f"{self.base}/telemetry/dc/+/measure"
        ac_topic = f"{self.base}/telemetry/ac/+/measure"
        print("Subscribing to:", dc_topic)
        client.subscribe(dc_topic)
        print("Subscribing to:", ac_topic)
        client.subscribe(ac_topic)

    def _on_message(self, client, userdata, msg):
        try:
            parts = msg.topic.split("/")
            kind = parts[-3]       # "dc" or "ac"
            device_id = parts[-2]
            payload = json.loads(msg.payload.decode())
            if kind == "dc" and self.on_dc_measure:
                self.on_dc_measure(device_id, payload)
            elif kind == "ac" and self.on_ac_measure:
                self.on_ac_measure(device_id, payload)
        except Exception as e:
            print("MQTT parse error:", e)

    def start(self):
        self.client.connect(self.host, self.port, keepalive=60)
        threading.Thread(target=self.client.loop_forever, daemon=True).start()

    def publish_switch(self, switch_id: str, state: str, channel: str | None = None):
        """
        Publishes ON/OFF to your normalized topic:
          base/control/switch/<switchId>/[chX/]<set>
        """
        topic = f"{self.base}/control/switch/{switch_id}"
        if channel:
            topic += f"/{channel}"
        topic += "/set"
        self.client.publish(topic, state)
