import os
import pytest
import sqlite3
import skabenclient.managers as mgr
from skabenclient.config import Config
from skabenclient.tests.mock import schemas

@pytest.fixture
def sqlite(request):

    def _dec(db_name, schema=None):
        conn = sqlite3.connect(db_name,
                               detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()
        if schema:
            cursor.execute(schema)
        def _finalize():
            cursor.close()
            conn.close()
        request.addfinalizer(_finalize)
        return cursor

    return _dec


def test_base_manager(write_config):
    path = write_config({'dev_type': 'test'})
    config = Config(path)
    base = mgr.BaseManager(config)
    
    assert base.reply_channel == 'test' + 'ask'


def test_db_fixture(make_db, sqlite):
    test_cursor = sqlite(make_db, schemas.test)
    test_cursor.execute("PRAGMA table_info(test)")
    rows = test_cursor.fetchall()
    assert list([r[1] for r in rows]) == ['id', 'uid', 'sound']


def test_plot_manager(get_root):
    config_path = os.path.join(get_root, 'res', 'test_config.yml')
    manager = mgr.PlotManager(config_path)
    test_config = {'device': 'testing',
                   'list_one': ['one', 'two', 3],
                   'list_two': ['this', 'is', 'conf']}

    manager.from_dict(test_config)
    manager.write()
    manager.from_file(config_path)

    assert manager.config == test_config
