import os
import shutil
import pytest
from flask import url_for, send_from_directory, jsonify

from skabenclient.loaders import HTTPLoader
from skabenclient.config import SystemConfig, DeviceConfigExtended, DeviceConfig


REMOTE_DIR = os.path.join(os.path.dirname(__file__), "res")
LOCAL_DIR = os.path.join(os.path.dirname(__file__), "temp")
ASSETS_ROOT = os.path.join(LOCAL_DIR, "assets")
ASSET_PATHS = {
    'test': '',
    'sound': '',
    'another': '',
}

if not os.path.exists(LOCAL_DIR):
    os.mkdir(LOCAL_DIR)


def read_bin(fpath):
    with open(fpath, 'rb') as fh:
        return fh.read()


@pytest.fixture
def asset_root(get_config, default_config, request):

    def _wrap(system_config):

        system_config = get_config(SystemConfig, default_config('sys'))
        system_config.root = LOCAL_DIR
        system_config.data['asset_root'] = ASSETS_ROOT
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
def get_extended_config(monkeypatch, get_config, default_config, asset_root):
    system_config = get_config(SystemConfig, default_config('sys'))
    system_config.root = LOCAL_DIR
    # create assets
    system_config = asset_root(system_config)
    dev_config_base = get_config(DeviceConfig, default_config('dev'))  # create for config path
    # get extended from config path, make assets subdirectories on init
    monkeypatch.setattr(DeviceConfigExtended, 'asset_paths', ASSET_PATHS)
    dev_config = DeviceConfigExtended(dev_config_base.config_path, system_config)
    return dev_config


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


def test_make_asset_paths(get_extended_config, remove_assets):
    """test makes asset dirs"""
    dev_config = get_extended_config
    dev_config.make_asset_paths()

    assert dev_config.asset_paths == ASSET_PATHS
    for dir_name in ASSET_PATHS:
        path = os.path.join(ASSETS_ROOT, dir_name)
        assert dev_config.asset_paths.get(dir_name) == path
        assert os.path.exists(os.path.join(ASSETS_ROOT, dir_name)), f"{dir_name} was not created"


def test_make_asset_paths_from_list(get_extended_config, remove_assets):
    """test makes asset dirs"""
    dev_config = get_extended_config
    asset_dirs = ["new", "asset", "dirs"]
    dev_config.asset_paths = {}
    dev_config.make_asset_paths(asset_dirs)

    assert list(dev_config.asset_paths.keys()) == asset_dirs
    for dir_name in asset_dirs:
        path = os.path.join(ASSETS_ROOT, dir_name)
        assert dev_config.asset_paths.get(dir_name) == path
        assert os.path.exists(os.path.join(ASSETS_ROOT, dir_name)), f"{dir_name} was not created"


def test_update_asset_paths(get_extended_config, remove_assets):
    """test makes asset dirs"""
    dev_config = get_extended_config
    asset_dirs = ["new", "asset", "dirs"]
    asset_pre_paths = [_ for _ in dev_config.asset_paths]
    dev_config.make_asset_paths(asset_dirs)

    assert list(dev_config.asset_paths.keys()) == asset_pre_paths + asset_dirs


@pytest.mark.skip(reason='virtualbox shared folder')
def test_clear_asset_paths(get_extended_config):
    dev_config = get_extended_config
    dev_config.make_asset_paths()

    dir_paths = [_ for _ in dev_config.asset_paths.values()]
    for path in dir_paths:
        assert os.path.exists(path)

    dev_config.clear_asset_paths()
    assert dev_config.asset_paths == {}
    for path in dir_paths:
        assert not os.path.exists(path)


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

    dev_config = get_extended_config
    dev_config.make_asset_paths()

    assert dev_config.asset_paths

    result = dev_config.parse_files({key: url})
    pick = result.get(key)

    assert pick
    assert pick.get("hash") == key
    assert pick.get("url") == url
    assert pick.get("local_path") == os.path.join(local_dir, fname)
    assert pick.get("loaded") is False
    assert pick.get("file_type") == dirname
    assert dev_config.data["assets"][key]["url"] == url


def test_files_parse_local_dir_not_exists(get_extended_config, get_file_vars):
    """test raise exception when local irectory for file type was not created"""
    key, dirname, fname, url, local_dir = get_file_vars
    dirname = 'non_exists'

    dev_config = get_extended_config
    dev_config.parse_files({key: url})
    with pytest.raises(Exception) as exc:
        assert str(exc.value) == f"no local directory was created for `{dirname}` type of files"


def test_files_parse_local_file_asset_exists(get_extended_config, get_file_vars):
    """test asset with flag loaded: True should not be updated"""
    key, dirname, fname, url, local_dir = get_file_vars

    dev_config = get_extended_config
    dev_config.make_asset_paths()
    assets = dev_config.data['assets']
    test_dict = {"loaded": True}
    assets[key] = test_dict
    dev_config.parse_files({key: url})

    assert assets[key]
    assert not assets[key].get("url")


def test_files_get(live_server, get_extended_config):
    fname = 'snd.ogg'
    asset = "test_a"

    @live_server.app.route('/test/<filename>')
    def test_a(filename):
        return send_from_directory(REMOTE_DIR, filename)

    live_server.start()

    dev_config = get_extended_config
    dev_config.asset_paths = {asset: ''}
    dev_config.make_asset_paths()

    remote_path = os.path.join(REMOTE_DIR, fname)
    local_path = os.path.join(ASSETS_ROOT, asset, "sound.ogg")

    file_data = {
        "hash": "12345",
        "url": url_for("test_a", filename=fname, _external=True),
        "local_path": local_path
    }

    result = dev_config.get_file(file_data)
    live_server.stop()

    assert result == {file_data["hash"]: local_path}
    assert read_bin(remote_path) == read_bin(local_path)


def test_files_get_no_fname(live_server, get_extended_config):
    fname = 'snd.ogg'
    asset = "test_b"

    dev_config = get_extended_config
    dev_config.asset_paths = {asset: ''}
    dev_config.make_asset_paths()

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

    result = dev_config.get_file(file_data)
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
    dev_config = get_extended_config
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

    _as = dev_config.data["assets"]
    for item in download:
        _as.update({item["hash"]: item})
    dev_config.get_files_sync(download)

    for file in file_list:
        local_file = os.path.join(local_path, f"{file}.snd")
        assert _as[file]["loaded"]
        assert _as[file]["hash"] == file
        assert _as[file]["local_path"] == local_file
        assert remote_data == read_bin(local_file)

    live_server.stop()


def test_files_get_async(live_server, get_extended_config):
    dev_config = get_extended_config
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

    _as = dev_config.data["assets"]
    for item in download:
        _as.update({item["hash"]: item})
    dev_config.get_files_async(download)

    for file in file_list:
        local_file = os.path.join(local_path, f"{file}.snd")
        assert _as[file]["loaded"]
        assert _as[file]["hash"] == file
        assert _as[file]["local_path"] == local_file
        assert remote_data == read_bin(local_file)

    live_server.stop()


def test_get_json(live_server, get_extended_config):
    live_server.stop()
    dev_config = get_extended_config
    payload = {"test": "json"}

    @live_server.app.route("/json/test/api")
    def json_test_api():
        return jsonify(payload)

    live_server.start()
    res = dev_config.get_json(url_for("json_test_api", _external=True))

    assert res == payload


def test_live_server_has_no_function_scope_thats_why(live_server):

    @live_server.app.route("/json/test/api/fail/dict")
    def json_test_api_dict():
        return {"just": "dict"}

    @live_server.app.route("/json/test/api/fail/list")
    def json_test_api_list():
        return ["p", "b", "list"]

    @live_server.app.route("/json/test/api/fail/str")
    def json_test_api_str():
        return "stringvalue"

    @live_server.app.route("/json/test/api/fail/bin")
    def json_test_api_bin():
        return b"binarysomething"

    @live_server.app.route("/json/test/api/fail/int")
    def json_test_api_int():
        return 87654231

    live_server.start()


@pytest.mark.parametrize(("payload", "endpoint"), [
    ({"just": "dict"}, "dict"),
    (["just", "list"], "list"),
    ("stringvalue", "str"),
    (b"binarysomething", "bin"),
    (87654231, "int")
])
def test_get_json_fail(get_extended_config, payload, endpoint):
    dev_config = get_extended_config

    with pytest.raises(Exception) as exc:
        url = url_for(f"json_test_api_{endpoint}", _external=True)
        dev_config.get_json(url)
        assert exc.value == f"empty response, {url} didn't return valid JSON"


def test_full_config(live_server, get_extended_config):
    live_server.stop()

    json_norm = {"data": "api_b"}
    json_ext = {
        "menu_set": [
            {
                "audio": "MqmVaQ7L",
                "name": "menu action",
                "timer": -1
            }
        ],
    }

    @live_server.app.route('/full_test/<filename>')
    def full_test(filename):
        return send_from_directory(REMOTE_DIR, filename)

    @live_server.app.route('/full_sound/<filename>')
    def full_sound(filename):
        return send_from_directory(REMOTE_DIR, filename)

    @live_server.app.route('/full_check/<filename>')
    def full_check(filename):
        return send_from_directory(REMOTE_DIR, filename)

    @live_server.app.route('/api/a')
    def api_norm():
        return jsonify(json_norm)

    @live_server.app.route('/api/b')
    def api_ext():
        return jsonify(json_ext)

    live_server.start()

    fname = "snd.ogg"
    ftype = "full_test"
    fhash = "MqmVaQ7L"

    dev_config = get_extended_config
    dev_config.asset_paths = {}
    dev_config.data = {}
    dev_config.save()

    dev_config.make_asset_paths([ftype])

    FULL_EXAMPLE = {
        "file_list": {
            f"{fhash}": f"/{ftype}/{fname}",
        },
        "modes_normal": [
            url_for("api_norm", _external=True)
        ],
        "modes_extended": [
            url_for("api_ext", _external=True)
        ],
    }

    data = {**FULL_EXAMPLE}
    file_url = url_for(ftype, filename=fname, _external=True)
    download_files = [val for val in dev_config.parse_files(data.pop("file_list")).values()]
    for file in download_files:
        file.update({"url": file_url})

    ASSETS_EXPECTED = {
        fhash: {
            'file_type': ftype,
            'hash': fhash,
            'loaded': True,
            'local_path': os.path.join(ASSETS_ROOT, ftype, fname),
            'url': file_url,
        }
    }

    result = {
        "assets": dev_config.get_files_async(download_files),
        "norm": [dev_config.get_json(mode) for mode in data.pop("modes_normal")],
        "ext": [dev_config.get_json(mode) for mode in data.pop("modes_extended")],
    }

    assert result["norm"] == [json_norm]
    assert result["ext"] == [json_ext]
    assert result["assets"] == ASSETS_EXPECTED
