import os
import shutil
import pytest
from flask import url_for, send_from_directory

from skabenclient.loaders import HTTPLoader
from skabenclient.config import SystemConfig, DeviceConfigExtended, DeviceConfig


REMOTE_DIR = os.path.join(os.path.dirname(__file__), "res")
LOCAL_DIR = os.path.join(os.path.dirname(__file__), "temp")
ASSETS_ROOT = os.path.join(LOCAL_DIR, "assets")
ASSET_DIRS = ['test', 'sound', 'another']

if not os.path.exists(LOCAL_DIR):
    os.mkdir(LOCAL_DIR)


def read_bin(fpath):
    with open(fpath, 'rb') as fh:
        return fh.read()


@pytest.fixture
def assets_root(get_config, default_config, request):

    def _wrap(system_config):

        system_config = get_config(SystemConfig, default_config('sys'))
        system_config.root = LOCAL_DIR
        system_config.data['assets_path'] = ASSETS_ROOT
        return system_config

    return _wrap


@pytest.fixture(autouse=True)
def remove_assets():
    if not os.path.exists(ASSETS_ROOT):
        os.mkdir(ASSETS_ROOT)
    yield
    try:
        shutil.rmtree(ASSETS_ROOT, ignore_errors=True)
        assert not os.path.exists(ASSETS_ROOT)
    except:
        # shared folder on virtualbox 6.0
        pass


@pytest.fixture
def get_extended_config(monkeypatch, get_config, default_config, assets_root):
    system_config = get_config(SystemConfig, default_config('sys'))
    system_config.root = LOCAL_DIR
    # create assets
    system_config = assets_root(system_config)
    device_base = get_config(DeviceConfig, default_config('dev'))  # create for config path
    # get extended from config path, make assets subdirectories on init
    monkeypatch.setattr(DeviceConfigExtended, 'asset_dirs', ASSET_DIRS)
    device_extended = DeviceConfigExtended(device_base.config_path, system_config)
    return device_extended


@pytest.fixture
def files_serve(get_extended_config, liveserver):

    # NOT WORKING BECAUSE OF LIVE_SERVER_SCOPE NOT WORKING

    @liveserver.app.route('/test/<filename>')
    def file_test(filename):
        return send_from_directory(REMOTE_DIR, filename)

    @liveserver.app.route('/another/<filename>')
    def file_another(filename):
        return send_from_directory(REMOTE_DIR, filename)

    @liveserver.app.route('/sound/<filename>')
    def file_sound(filename):
        return send_from_directory(REMOTE_DIR, filename)

    liveserver.start()

    yield

    liveserver.stop()


def test_make_asset_dirs(get_extended_config, remove_assets):
    """test makes asset dirs"""
    device_extended = get_extended_config
    device_extended.make_asset_dirs()

    for dir_name in ASSET_DIRS:
        path = os.path.join(ASSETS_ROOT, dir_name)
        assert device_extended.asset_dirs == ASSET_DIRS
        assert device_extended.asset_paths
        assert device_extended.asset_paths.get(dir_name) == path
        assert os.path.exists(os.path.join(ASSETS_ROOT, dir_name)), f"{dir_name} was not created"


@pytest.fixture
def get_file_vars():
    key = "MqmVaQ7L"
    dirname = 'test'
    fname = 'test.txt'
    url = f"/{dirname}/{fname}"
    local_dir = os.path.join(ASSETS_ROOT, dirname)

    return [key, dirname, fname, url, local_dir]


def test_files_parse_normal(get_extended_config, get_file_vars):
    """test parse `file_list` config field"""
    key, dirname, fname, url, local_dir = get_file_vars

    device = get_extended_config
    device.make_asset_dirs()

    assert device.asset_paths

    result = device.parse_files({key: url})
    pick = result.get(key)

    assert pick
    assert pick.get("hash") == key
    assert pick.get("url") == url
    assert pick.get("local_path") == os.path.join(local_dir, fname)
    assert pick.get("loaded") is False
    assert device.data["assets"][key]["url"] == url


def test_files_parse_local_dir_not_exists(get_extended_config, get_file_vars):
    """test raise exception when local irectory for file type was not created"""
    key, dirname, fname, url, local_dir = get_file_vars
    dirname = 'non_exists'

    device = get_extended_config
    device.parse_files([{key: url}])
    with pytest.raises(Exception) as exc:
        assert str(exc.value) == f"no local directory was created for `{dirname}` type of files"


def test_files_parse_local_file_asset_exists(get_extended_config, get_file_vars):
    """test asset with flag loaded: True should not be updated"""
    key, dirname, fname, url, local_dir = get_file_vars

    device = get_extended_config
    device.make_asset_dirs()
    assets = device.data['assets']
    test_dict = {"loaded": True}
    assets[key] = test_dict
    device.parse_files([{key: url}])

    assert assets[key]
    assert not assets[key].get("url")


def test_files_get(live_server, get_extended_config):
    fname = 'snd.ogg'
    asset = "test_a"

    @live_server.app.route('/test/<filename>')
    def test_a(filename):
        return send_from_directory(REMOTE_DIR, filename)

    live_server.start()

    device = get_extended_config
    device.asset_dirs = [asset]
    device.make_asset_dirs()

    remote_path = os.path.join(REMOTE_DIR, fname)
    local_path = os.path.join(ASSETS_ROOT, asset, "sound.ogg")

    file_data = {
        "hash": "12345",
        "url": url_for("test_a", filename=fname, _external=True),
        "local_path": local_path
    }

    result = device.get_file(file_data)
    live_server.stop()

    assert result == {file_data["hash"]: local_path}
    assert read_bin(remote_path) == read_bin(local_path)


def test_files_get_no_fname(live_server, get_extended_config):
    fname = 'snd.ogg'
    asset = "test_b"

    device = get_extended_config
    device.asset_dirs = [asset]
    device.make_asset_dirs()

    remote_path = os.path.join(REMOTE_DIR, fname)
    local_path = os.path.join(ASSETS_ROOT, asset)

    @live_server.app.route('/test/<filename>')
    def test_b(filename):
        return send_from_directory(REMOTE_DIR, filename)

    live_server.start()

    file_data = {
        "hash": "12345",
        "url": url_for(asset, filename=fname, _external=True),
        "local_path": local_path
    }

    result = device.get_file(file_data)
    local_path_result = os.path.join(local_path, fname)
    live_server.stop()

    assert result == {file_data["hash"]: local_path_result}
    assert read_bin(remote_path) == read_bin(local_path_result)


def gen_file_data(name, url, path, hash=None):
    return {
        "name": name,
        "url": url,
        "local_path": os.path.join(ASSETS_ROOT, path),
        "hash": hash if hash else name
    }


def test_files_get_sync(live_server, get_extended_config):
    device = get_extended_config
    fname = "snd.ogg"
    local_path = os.path.join(ASSETS_ROOT, "sound")
    remote_data = read_bin(os.path.join(REMOTE_DIR, fname))
    file_list = ["file_a", "file_b", "file_c"]

    @live_server.app.route('/sound/<filename>')
    def test_sync_file_a(filename):
        return send_from_directory(REMOTE_DIR, filename)

    @live_server.app.route('/sound/<filename>')
    def test_sync_file_b(filename):
        return send_from_directory(REMOTE_DIR, filename)

    @live_server.app.route('/sound/<filename>')
    def test_sync_file_c(filename):
        return send_from_directory(REMOTE_DIR, filename)

    live_server.start()

    def get_data(name):
        return gen_file_data(f"{name}",
                             url_for(f"test_sync_{name}", filename=fname, _external=True),
                             os.path.join(local_path, f"{name}.snd"))

    download = [get_data(name) for name in file_list]

    _as = device.data["assets"]
    for item in download:
        _as.update({item["hash"]: item})
    device.get_files_sync(download)

    for file in file_list:
        local_file = os.path.join(local_path, f"{file}.snd")
        assert _as[file]["loaded"]
        assert _as[file]["hash"] == file
        assert _as[file]["local_path"] == local_file
        assert remote_data == read_bin(local_file)

    live_server.stop()


def test_files_get_async(live_server, get_extended_config):
    device = get_extended_config
    fname = "snd.ogg"
    local_path = os.path.join(ASSETS_ROOT, "sound")
    remote_data = read_bin(os.path.join(REMOTE_DIR, fname))
    file_list = ["fileas_a", "fileas_b", "fileas_c"]

    @live_server.app.route('/sound/<filename>')
    def test_async_fileas_a(filename):
        return send_from_directory(REMOTE_DIR, filename)

    @live_server.app.route('/sound/<filename>')
    def test_async_fileas_b(filename):
        return send_from_directory(REMOTE_DIR, filename)

    @live_server.app.route('/sound/<filename>')
    def test_async_fileas_c(filename):
        return send_from_directory(REMOTE_DIR, filename)

    live_server.start()

    def get_data(name):
        return gen_file_data(f"{name}",
                             url_for(f"test_async_{name}", filename=fname, _external=True),
                             os.path.join(local_path, f"{name}.snd"))

    download = [get_data(name) for name in file_list]

    _as = device.data["assets"]
    for item in download:
        _as.update({item["hash"]: item})
    device.get_files_async(download)

    for file in file_list:
        local_file = os.path.join(local_path, f"{file}.snd")
        assert _as[file]["loaded"]
        assert _as[file]["hash"] == file
        assert _as[file]["local_path"] == local_file
        assert remote_data == read_bin(local_file)

    live_server.stop()

