import os
import logging
import sqlite3
import netifaces as netif

import skabenproto as sk
from skabenclient.helpers import make_event

sqlite3.register_adapter(bool, int)
sqlite3.register_converter('bool', lambda x: bool(int(x)))


class BaseManager:
    """
       Basic context manager abstract class
    """

    event = dict()

    def __init__(self, config):
        self.config = config
        self.q_int = config.get('q_int')
        if not self.q_int:
            raise Exception('internal queue not declared')
        self.q_ext = config.get('q_ext')
        if not self.q_ext:
            raise Exception('external (to mqtt) queue not declared')
        # keepalive TS management
        self.ts_fname = os.path.join(os.getcwd(), 'ts')
        if not os.path.exists(self.ts_fname):
            with open(self.ts_fname, 'w') as fh:
                fh.write('0')
        self.ts = self._last_ts()
        self.dev_type = config.get('dev_type')
        self.uid = config.get('uid')
        self.reply_channel = self.dev_type + 'ask'

    def get_ip_addr(self):
        """ Get IP address by interface name """
        try:
            iface = self.config.get('iface')
            self.ip = netif.ifaddresses(iface)[netif.AF_INET][0]['addr']
            return self.ip
        except Exception:
            raise

    def _last_ts(self):
        """ Read previous timestamp value from 'ts' file """
        with open(self.ts_fname, 'r') as fh:
            t = fh.read().rstrip()
            return int(t)

    def rewrite_ts(self, new_ts):
        """ Write timestamp value to file 'ts' """
        with open(self.ts_fname, 'w') as fh:
            fh.write(str(new_ts))

    def __enter__(self):
        return self

    def __exit__(self, *err):
        return


class MQTTManager(BaseManager):
    """ MQTT context manager
        parsing mqtt messages, send responses, proceed to device handlers
    """

    def __init__(self, config):
        super().__init__(config)

        # command table
        self.reactions = {
            "PING": self.pong,
            "WAIT": self.wait,
            "CUP": self.local_update,
            "SUP": self.local_send
        }

    def manage(self, event):
        """ Manage event from MQTT
            Command parsing and event routing
        """
        self.event = event

        my_ts = self._last_ts()
        event_ts = int(event.payload.get('ts', '-1'))

        if event.server_cmd == 'WAIT':
            # push me to the future
            self.rewrite_ts(event_ts + event.payload['timeout'])
            return

        if event_ts < my_ts:
            # ignoring messages from the past
            if event.server_cmd not in ('CUP', 'SUP'):
                return

        # update local ts from event
        self.rewrite_ts(event_ts)

        try:
            return self.reactions[self.event.server_cmd]()
        except KeyError:
            raise Exception('unrecognized command: {}'
                            .format(self.event.data.get("command")))

    def pong(self):
        """ Send PONG packet via MQTT """
        with sk.PacketEncoder() as p:
            packet = p.load('PONG',
                            dev_type=self.reply_channel,
                            uid=self.uid)
            encoded = p.encode(packet, self.ts)
            self.q_ext.put(encoded)

    def wait(self):
        """ Waiting for timeout """
        to = self.event.payload.get('timeout', 0)\
            + self.event.payload.get('ts')
        self.skip_until = to

    def local_update(self):
        """ Updating local device state from MQTT event
            Event should be handled by device handler respectively
        """
        event = make_event('device', 'update', self.event.payload)
        self.q_int.put(event)

    def local_send(self, fields=None):
        """ Send local config via MQTT """
        event = make_event('device', 'send', fields)
        self.q_int.put(event)

    def __repr__(self):
        return '<PacketManager>'


class DBManager(BaseManager):
    """
        Database interface for basic CRUD operations
    """

    columns = list()
    tables = list()

    structure = {
        'term': ('term', 'term_menu', 'term_text'),
        'lock': ('lock',),
    }

    def __init__(self, config):
        super().__init__(config)
        self.conn = sqlite3.connect(config['db_name'],
                                    detect_types=sqlite3.PARSE_DECLTYPES)
        self.conn.row_factory = sqlite3.Row
        # get db structure based on device type
        try:
            self.tables = self.structure.get(config.get('dev_type'))
        except Exception:
            logging.exception('cannot determine database structure for '
                              'device type {}'.format(config.get('dev_type')))
            raise

    def _istable(self, table_name):
        """ Checking if table name exists """
        if table_name in self.tables:
            return True
        else:
            raise Exception('TABLE name <{}> not in {}'
                            .format(table_name, self.tables))

    def _iscolumn(self, table_name, column_name):
        """ Checking if column name exists """
        c = self.conn.cursor()
        q = """ SELECT COUNT(*)
                AS CNTREC FROM pragma_table_info({})
                WHERE name = ? """.format(table_name)
        c.execute(q, (column_name, ))
        res = c.fetchall()
        if res and res > 0:
            return True

    def _column_list(self, table_name):
        """ Get table structure """
        columns = list()
        c = self.conn.cursor()
        self._istable(table_name)
        q = """ PRAGMA table_info(%s) """ % table_name
        c.execute(q)
        res = c.fetchall()
        for r in res:
            if r['name'] != 'id':
                columns.append(r['name'])
        return columns

    def select(self, table_name, column=None, value=None, target_col=None):
        """ Select from database """
        self._istable(table_name)
        sel = '*'  # by default - select all fields
        if target_col and isinstance(target_col, (list, tuple, set)):
            col_list = self._column_list(table_name)
            # all select targets are legitimate column name presented in schema
            if set(target_col).issubset(col_list):
                sel = ', '.join(target_col)
        c = self.conn.cursor()
        if column and value:
            q = """ SELECT {} FROM {} WHERE {} = ? """\
                .format(sel, table_name, column)
            c.execute(q, (value,))
        else:
            q = """ SELECT {} FROM {} """.format(sel, table_name)
            c.execute(q)
        res = c.fetchall()
        if res:
            # tuple of ever matching rows as dicts
            return list(dict(r) for r in res)

    def upd_from_dict(self, table_name, uid, data):
        """ Update database from dictionary """
        self._istable(table_name)
        col_list = self._column_list(table_name)
        filtered = dict()
        q = None
        upd_vals = None

        for col in data.keys():
            if col in col_list:
                filtered[col] = data[col]

        try:
            # insert if not exists else update
            if not self.select(table_name, 'uid', uid):
                args = ','.join(filtered.keys())
                upd_vals = list(filtered.values())
                q_marks = ','.join(list('?' * len(upd_vals)))
                q = """ INSERT INTO {} (uid, {}) VALUES (?, {}) """\
                    .format(table_name, args, q_marks)
                self.conn.execute(q, [uid, ] + upd_vals)
            else:
                args = ', '.join(list('{} = ?'.format(k)
                                      for k in filtered.keys()))
                upd_vals = list(filtered.values())
                upd_vals.append(uid)
                q = """ UPDATE {} SET {} WHERE uid = ? """\
                    .format(table_name, args)
                self.conn.execute(q, upd_vals)
            return True
        except Exception:
            logging.exception('ERROR:\n\tquery> {}\n\targs> {}'
                              .format(q, upd_vals))
            raise

    def commit(self):
        """ Commit database changes """
        try:
            self.conn.commit()
            logging.debug('DB updated.')
            return True
        except Exception:
            self.rollback()

    def rollback(self):
        """ Rollback database changes """
        self.conn.rollback()
        logging.error('DB rollback.')

    def clear_table(self, table_name):
        """ Clear table data """
        if not self._istable(table_name):
            logging.error(f'trying to clear non-existent table: {table_name}')
            return
        try:
            self.conn.execute('DELETE FROM {}'.format(table_name))
            logging.debug('cleared table {}'.format(table_name))
            self.commit()
            return True
        except Exception:
            logging.exception(f'failed to delete from {table_name}')
            self.rollback()
            raise

    def create_default(self, table_name, uid=None):
        """ Create empty table """
        try:
            if uid:
                q = f""" INSERT INTO {table_name} (uid) VALUES (?) """
                self.conn.execute(q, (uid, ))
            else:
                q = f""" INSERT INTO {table_name} DEFAULT VALUES """
                self.conn.execute(q)
            self.commit()
            return True
        except Exception:
            logging.exception('cannot create default values for %s'
                              % table_name)
            self.rollback()
            raise


class DeviceManager(DBManager):

    def __init__(self, config):
        super().__init__(config)
        self.dev = config.get('end_device')
        if not self.dev:
            raise Exception('missing end device')
        # send IP on start - NOPE, NOPE, NOPE
        # self.local_send({'ip': self.config['ip']})

    def manage(self, event):
        if event.cmd == 'update':
            # receive update from server
            logging.debug('event is {} WITH DATA {}'.format(event, event.data))
            current_conf = self.get_running_conf()
            task_id = event.data.get('task_id', '12345')
            response = 'ACK'
            try:
                self.local_update(event.data)
                self.reset_device()
            except Exception:
                response = 'NACK'
                logging.exception('cannot apply new config')
                self.dev.plot.update(current_conf)
            finally:
                self.confirm_update(task_id, response)
        elif event.cmd == 'send':
            # send to server without local db update
            logging.debug('event is {} - sending data to server'.format(event))
            self.local_send(event.data)
        elif event.cmd == 'input':
            # update local db, send to server
            logging.debug('event is {} - input: {}'.format(event, event.data))
            if event.data:
                self.local_update(event.data)
                self.local_send(event.data)
            else:
                logging.error('missing data from event: {}'.format(event))
        elif event.cmd == 'reload':
            # just reload device with current plot
            logging.debug('event is {} - reloading device'.format(event))
            self.reset_device()
        else:
            logging.error('bad event {}'.format(event))

    def get_running_conf(self):
        try:
            current = self.select(self.dev_type, 'uid', self.uid)
            if not current:
                if self.create_default(self.dev_type, self.uid):
                    # second attempt
                    current = self.select(self.dev_type, 'uid', self.uid)
            elif len(current) > 1:
                logging.error('too many records in DB')
                current = current[-1]
                # self.remote_request()
            if current:
                return current[0]
        except Exception:
            logging.exception('cannot get running config')
            raise

    def local_update(self, data):
        # no commit/rollback here, do not use directly
        uid = data.get('uid')  # routine used for additional tables too
        if not uid:
            logging.error('missing PK (uid) for update: {}'.format(data))
        return self.upd_from_dict(self.dev_type, uid, data)

    def local_send(self, data):
        if not data or not isinstance(data, dict):
            logging.error('missing data to send')
            return
        data = {k: v for k, v in data.items() if k not in ('id', 'uid')}
        # send update to server DB
        with sk.PacketEncoder() as p:
            packet = p.load('SUP',
                            uid=self.uid,
                            dev_type=self.reply_channel,
                            payload=data)
            # add IP as additional field
            # packet.payload.update({'ip': self.config['ip']})
            encoded = p.encode(packet, self.ts)
            self.q_ext.put(encoded)

    def remote_request(self, keys=None):
        current = self.get_running_conf()
        if keys:
            payload = {'request': tuple(k for k in current if k in keys)}
        else:
            payload = {'request': 'all'}  # full conf

        with sk.PacketEncoder() as p:
            packet = p.load('CUP',
                            dev_type=self.reply_channel,
                            uid=self.uid,
                            payload=payload)
            encoded = p.encode(packet, self.ts)
            self.q_ext.put(encoded)

    def confirm_update(self, task_id, packet_type='ACK'):
        # confirm to server that we received and applied update
        # should be initialized only after device handler success
        with sk.PacketEncoder() as p:
            packet = p.load(packet_type,
                            dev_type=self.reply_channel,
                            uid=self.uid,
                            task_id=task_id)
            encoded = p.encode(packet, self.ts)
            self.q_ext.put(encoded)

    def reset_device(self):
        # logging.error('call reset method of abstract class DeviceHandler')
        current_conf = self.get_running_conf()
        self.dev.plot.update(current_conf)
