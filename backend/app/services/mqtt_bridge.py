import json
import ssl
import threading
import paho.mqtt.client as mqtt

try:
    import certifi  # for a reliable CA bundle on Windows
    CA_CERTS = certifi.where()
except Exception:
    CA_CERTS = None

class MQTTBridge:
    """
    Subscribes to DC and AC telemetry; can publish switch commands.
    Works with HiveMQ Cloud (TLS + auth) and plain brokers.
    """

    def __init__(
            self,
            host: str,
            port: int,
            base: str,
            on_dc_measure=None,
            on_ac_measure=None,
            *,
            username: str | None = None,
            password: str | None = None,
            use_tls: bool = False,
            use_ws: bool = False,
            ws_path: str = "/mqtt",
            keepalive: int = 60,
            client_id: str | None = None,
    ):
        self.host, self.port = host, port
        self.base = base.rstrip("/")
        self.on_dc_measure = on_dc_measure
        self.on_ac_measure = on_ac_measure
        self.keepalive = keepalive

        transport = "websockets" if use_ws else "tcp"
        self.client = mqtt.Client(client_id=client_id or "", protocol=mqtt.MQTTv311, transport=transport)

        # Auth (HiveMQ Cloud)
        if username:
            self.client.username_pw_set(username, password or "")

        # TLS (HiveMQ Cloud requires it on 8883)
        if use_tls:
            if CA_CERTS:
                self.client.tls_set(ca_certs=CA_CERTS, certfile=None, keyfile=None,
                                    cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
            else:
                # fallback to system store
                self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
            self.client.tls_insecure_set(False)

        # WebSocket path (if applicable)
        if use_ws:
            self.client.ws_set_options(path=ws_path)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    # Topics
    @property
    def topic_dc(self) -> str:
        return f"{self.base}/telemetry/dc/+/measure"

    @property
    def topic_ac(self) -> str:
        return f"{self.base}/telemetry/ac/+/measure"

    # Callbacks
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        print("MQTT connected, rc=", rc)
        print("Subscribing to:", self.topic_dc)
        client.subscribe(self.topic_dc, qos=1)
        print("Subscribing to:", self.topic_ac)
        client.subscribe(self.topic_ac, qos=1)
        client.publish(f"{self.base}/backend/status", payload="online", qos=1, retain=True)
        print(f"{self.base}/backend/status")

    def _on_message(self, client, userdata, msg):
        try:
            parts = msg.topic.split("/")
            # .../telemetry/{dc|ac}/{deviceId}/measure
            kind = parts[-3]
            device_id = parts[-2]
            payload = json.loads(msg.payload.decode("utf-8"))
            if kind == "dc" and self.on_dc_measure:
                self.on_dc_measure(device_id, payload)
            elif kind == "ac" and self.on_ac_measure:
                self.on_ac_measure(device_id, payload)
        except Exception as e:
            print("MQTT parse error:", e)

    # Control publish
    def publish_switch(self, switch_id: str, state: str, channel: str | None = None):
        ch = channel or "ch1"
        topic = f"{self.base}/control/switch/{switch_id}/{ch}/set"
        self.client.publish(topic, state.upper(), qos=1, retain=False)

    def start(self):
        def _loop():
            self.client.connect(self.host, self.port, keepalive=self.keepalive)
            self.client.loop_forever()
        threading.Thread(target=_loop, daemon=True).start()
