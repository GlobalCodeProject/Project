import paho.mqtt.client as mqtt

c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)  # paho-mqtt v2.x
rc = c.connect("localhost", 1883, 60)
assert rc == 0, f"Connect failed rc={rc}"
info = c.publish(
    "spo/v1/telemetry/dc/dc-esp32-1/measure",
    '{"v": 12.2, "i": 0.40, "p": 4.88}'
)
info.wait_for_publish()
print("Published?", info.is_published())
c.disconnect()
