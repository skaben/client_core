import json

class MockMessage:

    def __init__(self, packet):
        self.topic = packet[0]
        self.payload = packet[1]
        self.decoded = json.loads(self.payload.decode('utf-8'))


class MockQueue:

    def __init__(self):
        self.data = []

    def put(self, value):
        self.data.append(value)

    def get(self):
        return self.data.pop()