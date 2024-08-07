import asyncio
import collections.abc
import concurrent.futures
import logging
import logging.handlers
import multiprocessing as mp
import os
import shutil
from typing import Any, List, TextIO, Union

import yaml

from skabenclient.helpers import FileLock, get_ip, get_mac
from skabenclient.loaders import HTTPLoader, get_yaml_loader
from skabenclient.logger import CoreLogger

ExtendedLoader = get_yaml_loader()
_mapping = collections.abc.Mapping


class Config:

    """ Abstract config class

        Provides methods for reading and writing .yml config file with filelock
    """

    # essential config
    minimal_essential_conf = dict()
    files_local = dict()

    # fields should not be stored in .yml
    not_stored_keys = [
        "FORCE",
        "NESTED"
    ]

    def __init__(self, config_path: str):
        self.data = dict()
        self.config_path = config_path
        if not config_path:
            raise Exception(f'config path is missing for {self}')
        current = self.read()
        self.update(current)

    def _yaml_load(self, target: TextIO) -> dict:
        """Loads yaml from given file"""
        result = yaml.load(target, Loader=ExtendedLoader)
        if not result:
            raise EOFError(f"{target} cannot be loaded")
        return result

    def read(self):
        """ Reads from config file """
        try:
            with FileLock(self.config_path):
                with open(self.config_path, 'r') as fh:
                    return self._yaml_load(fh)
        except Exception:
            raise

    def write(self, data: dict = None, mode: str = 'w'):
        """ Writes to config file """
        if not data:
            data = self.data
        try:
            data = self._filter(data)
            with FileLock(self.config_path):
                with open(self.config_path, mode) as fh:
                    dump = yaml.dump(self._filter(data), default_flow_style=False)
                    fh.write(dump)
        except Exception:
            raise

    def get(self, key: str, arg: Any = None) -> Any:
        """Get compatibility wrapper"""
        return self.data.get(key, arg)

    def set(self, key: str, val: str) -> dict:
        """Set compatibility wrapper"""
        return self.update({key: val})

    def update(self, payload: dict) -> dict:
        """Updates local namespace from payload with basic filtering"""
        update_target = self.data
        if payload.get("FORCE"):
            # destructive update
            update_target = self.minimal_essential_conf
            self.files_local = {}
            self.data = {**self.minimal_essential_conf, **self._filter(payload)}
        elif payload.get("NESTED"):
            # nested update
            self.data = self._update_nested(update_target, self._filter(payload))
        else:
            self.data.update(**self._filter(payload))
        return self.data

    def _update_nested(self, target: dict, update: _mapping) -> dict:
        """Update nested dictionaries"""
        for k, v in update.items():
            try:
                if isinstance(v, _mapping):
                    key = target.get(k)
                    if key is None:
                        target.update({k: v})
                        continue
                    elif not isinstance(key, _mapping):
                        target[k] = {}
                    target[k] = self._update_nested(target[k], v)
                else:
                    target[k] = v
            except Exception as exc:
                raise Exception(f"TARGET: {target} ({type(target)}) "
                                f"KEY: {k} ({type(target)}) updated by VAL: {v} \n {exc}")
        return dict(target)

    def _filter(self, payload: dict) -> Union[dict, bool]:
        """Filter keys starting with underscore and by filtered keys list"""
        return {k: v for k, v in payload.items() if k not in self.not_stored_keys or not k.startswith('_')}


class SystemConfig(Config):
    """System read-only configuration"""

    logger_instance = None

    def __init__(self, config_path: str = None, root: str = None):
        self.data = {}
        self.root = root if root else os.path.abspath(os.getcwd())
        super().__init__(config_path)

        self.DEBUG = self.get('debug')
        iface = self.get('iface')

        if not iface:
            raise Exception('network interface missing in config')

        topic = self.get('topic')
        uid = get_mac(iface)

        # set PUB/SUB topics
        _publish = f'ask/{topic}'
        # 'all' reserved for broadcast messages
        _subscribe = [f"{topic}/all/#", f"{topic}/{uid}/#"]

        # update config with session values, this will not be saved to file
        self.update({
            'uid': uid,
            'ip': get_ip(iface),
            'q_int': mp.Queue(),
            'q_ext': mp.Queue(),
            'q_log': mp.Queue(),
            'pub': _publish,
            'sub': _subscribe,
        })

        self.log = CoreLogger(root=self.root,
                              logging_queue=self.get('q_log'),
                              internal_queue=self.get('q_int'),
                              debug=self.DEBUG)
        self.logger_instance = self.log.make_root_logger()

    def logger(self, name: str = None, level: int = logging.INFO) -> logging.Logger:
        if self.DEBUG:
            level = logging.DEBUG
        return self.log.make_logger(name=name, level=level, ext_level=self.get('external_logging'))

    def write(self, data: dict = None, mode: str = None) -> PermissionError:
        raise PermissionError('System config cannot be created automatically. '
                              'Seems like config file is missing or corrupted.')

    def __del__(self):
        """Clear loggers on instance delete"""
        if self.logger_instance:
            self.logger_instance.handlers.clear()
            del self.logger_instance


class DeviceConfig(Config):

    """
        Device configuration, read-write
    """

    minimal_essential_conf = {}

    def __init__(self, config_path: str):
        self.data = dict()
        self.not_stored_keys.extend(['message'])
        super().__init__(config_path)

    def write_default(self):
        """ Create config file and write default configuration to it """
        if not self.minimal_essential_conf:
            raise RuntimeError('minimal essential conf values is missing, '
                               'config file cannot be reset to defaults')
        try:
            self.data = self.minimal_essential_conf
            self.write()
            return self.data
        except PermissionError as e:
            raise PermissionError(f'config file write permission error: {e}')
        except Exception:
            raise

    def read(self):
        try:
            config = super().read()
            # make a consistency check
            if not set(self.minimal_essential_conf.keys()).issubset(set(config.keys())):
                # check failed, essential keys missing
                raise AttributeError
        except (EOFError, FileNotFoundError, yaml.YAMLError, AttributeError):
            # file is empty or not created or corrupted, rewrite with default conf
            config = self.write_default()
        except Exception:
            raise
        return config

    def load(self):
        """ Load and apply state from file """
        try:
            current_conf = self.read()
            if not current_conf:
                raise Exception('config inconsistency')
            for k in self.minimal_essential_conf:
                if k not in current_conf:
                    raise Exception('config inconsistency')
            return self.update(self.read())
        except Exception:
            return self.write_default()

    def save(self, payload: dict = None):
        """ Apply and save persistent state """
        if payload:
            self.update(payload)
        self.write(self.data)

    def current(self):
        """ Get current config """
        return self.data


class DeviceConfigExtended(DeviceConfig):
    """device config with extended API support"""

    minimal_essential_conf = {
        "assets": {}
    }

    asset_paths = {}  # directory paths by file types
    files_local = {}

    def __init__(self, config_path: str, system_config: SystemConfig):
        self.system = system_config
        self.logger = self.system.logger()
        self._update_paths(self.system.get("asset_types", []))
        asset_root = self.system.get('asset_root')
        if not asset_root:
            raise Exception('Assets directory not found. Parameter `asset_root` must be provided in system config')
        self.asset_root = os.path.join(self.system.root, asset_root)
        if not os.path.exists(self.asset_root):
            os.mkdir(self.asset_root)
        super().__init__(config_path)

    def make_asset_paths(self, asset_dirs: Union[list, bool] = None) -> dict:
        self._update_paths(asset_dirs)
        for dirname in self.asset_paths:
            dirpath = os.path.join(self.asset_root, dirname)
            if not os.path.exists(dirpath):
                os.mkdir(dirpath)
            self.asset_paths[dirname] = dirpath
        return self.asset_paths

    def clear_asset_paths(self):
        """not used in production"""
        try:
            for _dir in self.asset_paths.values():
                shutil.rmtree(_dir)
            self.asset_paths = {}
        except Exception as e:
            raise Exception(f"cannot remove assets dir: {e}")

    def _update_paths(self, dirs: list) -> dict:
        if dirs and isinstance(dirs, (list, tuple)):
            self.asset_paths.update({k: "" for k in dirs})
            return self.asset_paths

    def parse_files(self, files: dict) -> dict:
        if not self.asset_paths:
            raise Exception("asset directories was not created, run DeviceConfig.make_asset_paths(asset_dirs) first!")
        not_loaded = {}
        if files and isinstance(files, dict):
            assets = self.get('assets', {})

            for _hash, url in files.items():
                exists = assets.get(_hash)
                if exists and self.files_local.get(_hash):
                    continue

                file_type, orig_name = url.split("/")[-2:]
                if len(orig_name.split(".")) < 2:
                    raise NotImplementedError("URI without file extension not supported")

                local_dir = self.asset_paths.get(file_type)
                if not local_dir:
                    raise Exception(f"no local directory was created for `{file_type}` type of files")

                not_loaded.update({
                    _hash: {
                        "local_path": os.path.join(local_dir, orig_name),
                        "hash": _hash,
                        "url": url,
                        "file_type": file_type,
                    }
                })
                self.update({"assets": not_loaded, "NESTED": True})
        return not_loaded

    def get_file(self, file_data: dict) -> dict:
        try:
            with HTTPLoader(self.system) as loader:
                path = loader.get_file(file_data["url"], file_data["local_path"])
                if path:
                    self.set_file_loaded(file_data["hash"])
                    return {file_data["hash"]: path}
        except Exception as e:
            self.logger.exception(f'while loading file: {e}')

    async def download(self, files: List[dict]) -> dict:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.system.get("max_workers", 3))
        loop = asyncio.get_event_loop()
        for item in files:
            await loop.run_in_executor(executor, self.get_file, item)
        return self.data["assets"]

    def get_files_async(self, files: List[dict]):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.download(files))

    def get_files_sync(self, files: List[dict]):
        for item in files:
            self.get_file(item)
        return self.data["assets"]

    def set_file_loaded(self, _hash: str):
        self.files_local[_hash] = _hash

    def get_json(self, url: str) -> dict:
        with HTTPLoader(self.system) as loader:
            response = loader.get_json(url)
            if response == {}:
                raise Exception(f"empty response, {url} didn't return valid JSON")
            return response
