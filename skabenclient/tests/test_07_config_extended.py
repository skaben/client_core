import os
import shutil

import pytest

from skabenclient.config import DeviceConfig, DeviceConfigExtended, SystemConfig

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
    dev_config.data['assets'] = {key: {'test': 'file'}}
    dev_config.set_file_loaded(key)

    assert dev_config.data['assets'].get(key)
    assert dev_config.files_local.get(key)
    assert dev_config.parse_files({key: url}) == {}, 'file parsed twice'


def gen_file_data(name, url, path, hash=None):
    return {
        "name": name,
        "url": url,
        "local_path": os.path.join(ASSETS_ROOT, path),
        "hash": hash if hash else name
    }
