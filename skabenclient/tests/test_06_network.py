import os
import pytest
import requests
from flask import url_for, send_from_directory

from skabenclient.loaders import HTTPLoader
from skabenclient.config import SystemConfig


REMOTE_DIR = os.path.join(os.path.dirname(__file__), "res")
LOCAL_DIR = os.path.join(os.path.dirname(__file__), "temp")

if not os.path.exists(LOCAL_DIR):
    os.mkdir(LOCAL_DIR)

# basic live-server integration tests

def read_bin(fpath):
    with open(fpath, 'rb') as fh:
        return fh.read()


def test_add_endpoint_to_live_server(live_server):
    @live_server.app.route('/test-endpoint')
    def test_endpoint():
        return 'got it', 200

    live_server.start()

    res = requests.get(url_for('test_endpoint', _external=True))
    assert res.status_code == 200
    assert b'got it' in res.content

    live_server.stop()


def test_serve_file(live_server):
    path = (REMOTE_DIR, "snd.ogg")
    file_content = read_bin(os.path.join(*path))

    @live_server.app.route('/send-file')
    def send_file():
        return send_from_directory(*path)

    live_server.start()

    res = requests.get(url_for("send_file", _external=True))
    assert res.status_code == 200
    assert res.content == file_content, 'bad file'

    live_server.stop()


# try to get file

def test_http_loader(live_server, get_config, default_config):
    cfg = get_config(SystemConfig, default_config('sys'))
    path = os.path.join(REMOTE_DIR, "snd.ogg")
    local_file = "sound.ogg"

    live_server.start()

    with HTTPLoader(system_config=cfg, local_dir=LOCAL_DIR) as loader:
        getfile_path = loader.get(url_for("send_file", _external=True), local_file)

    live_server.stop()

    assert getfile_path == os.path.join(LOCAL_DIR, local_file)
    assert read_bin(getfile_path) == read_bin(path)

    os.remove(getfile_path)


URLS = [
    ("http://127.0.0.1/files/test.ogg", "test.ogg", "http://127.0.0.1")
]


@pytest.mark.parametrize("url, url_fname, url_base", URLS)
def test_http_loader_parse_url(url, url_fname, url_base, get_config, default_config):
    cfg = get_config(SystemConfig, default_config('sys'))
    with HTTPLoader(cfg, LOCAL_DIR) as loader:
        result = loader.parse_url(url)

    assert result.get("file") == url_fname, "url filename parsed wrong"
    assert result.get("base") == url_base, "url base parsed wrong"


def test_http_loader_no_ext_in_url(live_server, get_config, default_config):
    cfg = get_config(SystemConfig, default_config('sys'))

    live_server.start()

    with pytest.raises(Exception) as exc:
        with HTTPLoader(system_config=cfg, local_dir=LOCAL_DIR) as loader:
            loader.get(url_for("send_file", _external=True))

    live_server.stop()

    assert str(exc.value) == 'Target URL missing file extension. Provide local filename: '\
                             'HTTPLoader.get(remote_url, local_file="file.extension")'


def test_http_loader_has_ext_in_url(live_server, get_config, default_config):
    cfg = get_config(SystemConfig, default_config('sys'))
    fname = "snd.ogg"

    @live_server.app.route('/files/<filename>')
    def file_named(filename):
        return send_from_directory(REMOTE_DIR, filename)

    live_server.start()

    with HTTPLoader(system_config=cfg, local_dir=LOCAL_DIR) as loader:
        getfile_path = loader.get(url_for("file_named", filename=fname, _external=True))

    live_server.stop()

    assert getfile_path == os.path.join(LOCAL_DIR, fname)
    assert read_bin(getfile_path) == read_bin(os.path.join(REMOTE_DIR, fname))

    os.remove(getfile_path)

