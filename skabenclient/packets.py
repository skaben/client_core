import json
from typing import Optional


class BasePacket:
    """
        Base packet class
    """

    command = str()

    def __init__(self,
                 topic: str,
                 uid: Optional[str] = None,
                 timestamp: Optional[int] = None,
                 config_hash: Optional[str] = None):
        self.topic = "/".join([_ for _ in (topic, uid, self.command) if _ not in (None, "")])
        self.payload = {
            "timestamp": timestamp if timestamp else 0  # assign timestamp if provided
        }
        if config_hash:
            self.payload.update(hash=config_hash)

    def encode(self):
        try:
            payload = json.dumps(self.payload).encode('utf-8')
            return tuple((self.topic, payload))
        except Exception:
            raise

    def __repr__(self):
        return f"{self.topic} {self.payload}"

# ping packets


class PING(BasePacket):
    """
        Ping packet. Broadcast only.
    """
    def __init__(self,
                 topic: str,
                 uid: Optional[str] = None,
                 timestamp: Optional[int] = None):
        self.command = "ping"
        super().__init__(topic=topic,
                         uid=uid,
                         timestamp=timestamp)


class PONG(BasePacket):
    """
        PONG packet, send only in response to PING
        Should send timestamp value of PING
        Can send config hash as .conf attribute
    """
    def __init__(self,
                 topic: str,
                 uid: str,
                 timestamp: int,
                 config_hash: Optional[str] = None):
        self.command = "pong"
        super().__init__(topic=topic,
                         uid=uid,
                         timestamp=timestamp,
                         config_hash=config_hash)


class WAIT(BasePacket):
    """
        Sent in response of PONG, currently
        before sending another PONG client should either
        wait timeout or receive nowait-packet (CUP/SUP)
    """
    def __init__(self, topic: str, timeout: int, uid: str, timestamp: int):
        self.command = "wait"
        super().__init__(topic=topic,
                         uid=uid,
                         timestamp=timestamp)

        if not isinstance(timeout, int):
            try:
                timeout = round(int(timeout))
            except Exception:
                raise ValueError(f"bad timeout value: {timeout}")
        self.payload.update(timeout=timeout)


class ACK(BasePacket):
    """
        Confirm operations on previous packet as successful
        Should send ts of previous packet
    """
    def __init__(self, topic: str, task_id: str, uid: str, timestamp: int, config_hash: str):
        self.command = "ack"
        super().__init__(topic=topic,
                         uid=uid,
                         timestamp=timestamp,
                         config_hash=config_hash)
        self.payload.update(task_id=task_id)


class NACK(BasePacket):
    """
        Confirm operations on previous packet as unsuccessful
        Should send ts of previous packet
    """
    def __init__(self, topic: str, task_id: str, uid: str, timestamp: int, config_hash: str):
        self.command = "nack"
        super().__init__(topic=topic,
                         uid=uid,
                         timestamp=timestamp,
                         config_hash=config_hash)
        self.payload.update(task_id=task_id)


# packets with payload


class DataholdPacket(BasePacket):
    """
        Loaded packet basic class.
    """

    datahold = {}  # packet data load

    def __init__(self,
                 topic: str,
                 datahold: dict,
                 timestamp: int,
                 config_hash: Optional[str] = None,
                 uid: Optional[str] = None,
                 task_id: Optional[str] = None):
        super().__init__(topic=topic,
                         uid=uid,
                         timestamp=timestamp,
                         config_hash=config_hash)
        self.payload.update(datahold=datahold)  # отдельное пространство имен для данных
        if task_id:
            self.payload.update(task_id=task_id)


class INFO(DataholdPacket):
    """
        Multipurpose payload packet
    """
    def __init__(self,
                 topic: str,
                 datahold: dict,
                 uid: str,
                 timestamp: int,
                 task_id: Optional[str] = None):
        self.command = "info"
        super().__init__(topic=topic,
                         datahold=datahold,
                         timestamp=timestamp,
                         task_id=task_id,
                         uid=uid)


class SUP(DataholdPacket):
    """
        State Update - update server config and global dungeon state
    """
    def __init__(self,
                 topic: str,
                 datahold: dict,
                 uid: str,
                 timestamp: int,
                 task_id: Optional[str] = None):
        self.command = "sup"
        super().__init__(topic=topic,
                         datahold=datahold,
                         task_id=task_id,
                         uid=uid,
                         timestamp=timestamp)


class CUP(DataholdPacket):
    """
        Client/Config Update - update client config
    """
    def __init__(self,
                 topic: str,
                 datahold: dict,
                 task_id: str,
                 timestamp: int,
                 uid: Optional[str] = None,
                 config_hash: Optional[str] = None):
        self.command = "cup"
        super().__init__(topic=topic,
                         datahold=datahold,
                         task_id=task_id,
                         uid=uid,
                         timestamp=timestamp,
                         config_hash=config_hash)
