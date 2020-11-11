import os
import requests
from flask import url_for, send_from_directory

from skabenclient.loaders import HTTPLoader
from skabenclient.config import SystemConfig

files_dir = os.path.join(os.path.dirname(__file__), "res")

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
    path = (files_dir, "snd.ogg")
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

def test_get_file_by_loader(live_server, get_config, default_config):
    cfg = get_config(SystemConfig, default_config('sys'))
    path = os.path.join(files_dir, "snd.ogg")
    local_file = "sound.ogg"

    live_server.start()

    with HTTPLoader(system_config=cfg, local_dir=files_dir) as loader:
        getfile_path = loader.get(url_for("send_file", _external=True), local_file)

    assert getfile_path == os.path.join(files_dir, local_file)
    assert read_bin(getfile_path) == read_bin(path)

    os.remove(getfile_path)
    live_server.stop()

