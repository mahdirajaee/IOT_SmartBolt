import json

import paho.mqtt.client as PahoMQTT


class MyMQTT:
    def __init__(self, clientID, broker, port, notifier, clean_session=True):
        self.broker = broker
        self.port = port
        self.notifier = notifier
        self.clientID = clientID
        self._topics = []
        self._isSubscriber = False
        self._paho_mqtt = PahoMQTT.Client(callback_api_version=PahoMQTT.CallbackAPIVersion.VERSION1, client_id=clientID, clean_session=clean_session)
        self._paho_mqtt.on_connect = self.myOnConnect
        self._paho_mqtt.on_message = self.myOnMessageReceived
        self._paho_mqtt.on_disconnect = self.myOnDisconnect
        self._paho_mqtt.on_publish = self.myOnPublish

    def myOnConnect(self, paho_mqtt, userdata, flags, rc):
        print("Connected to %s with result code: %d" % (self.broker, rc))
        for topic in self._topics:
            self._paho_mqtt.subscribe(topic, 2)

    def myOnDisconnect(self, paho_mqtt, userdata, rc):
        if rc != 0:
            print("Unexpected disconnection from %s (rc: %d)" % (self.broker, rc))
        else:
            print("Disconnected from %s" % self.broker)

    def myOnMessageReceived(self, paho_mqtt, userdata, msg):
        self.notifier.notify(msg.topic, msg.payload)

    def myOnPublish(self, paho_mqtt, userdata, mid):
        print("Message %d published successfully" % mid)

    def myPublish(self, topic, msg):
        result = self._paho_mqtt.publish(topic, json.dumps(msg), 2)
        if result.rc != 0:
            print("Publish failed for topic %s (rc: %d)" % (topic, result.rc))
        return result

    def mySubscribe(self, topic):
        self._paho_mqtt.subscribe(topic, 2)
        self._isSubscriber = True
        if topic not in self._topics:
            self._topics.append(topic)
        print("subscribed to %s" % (topic))

    def start(self):
        self._paho_mqtt.connect(self.broker, self.port)
        self._paho_mqtt.loop_start()

    def unsubscribe(self):
        if (self._isSubscriber):
            for topic in self._topics:
                self._paho_mqtt.unsubscribe(topic)

    def stop(self):
        if (self._isSubscriber):
            for topic in self._topics:
                self._paho_mqtt.unsubscribe(topic)

        self._paho_mqtt.loop_stop()
        self._paho_mqtt.disconnect()
