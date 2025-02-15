import logging
import json
import importlib
import binascii
from typing import List
from types import SimpleNamespace
from neo3.core import cryptography

version = '0.5'

core_logger = logging.getLogger('neo3.core')
network_logger = logging.getLogger('neo3.network')
storage_logger = logging.getLogger('neo3.storage')


def load_class_from_path(path_and_class: str):
    """
    Dynamically load a class from a module at the specified path
    Args:
        path_and_class: relative path where to find the module and its class name
        i.e. 'neo3.<package>.<package>.<module>.<class name>'
    Raises:
        ValueError: if the Module or Class is not found.
    Returns:
        class object
    """
    try:
        module_path = '.'.join(path_and_class.split('.')[:-1])
        module = importlib.import_module(module_path)
    except ImportError as err:
        raise ValueError(f"Failed to import module {module_path} with error: {err}")

    try:
        class_name = path_and_class.split('.')[-1]
        class_obj = getattr(module, class_name)
        return class_obj
    except AttributeError as err:
        raise ValueError(f"Failed to get class {class_name} with error: {err}")


class IndexableNamespace(SimpleNamespace):
    def __len__(self):
        return len(self.__dict__)

    def __getitem__(self, key):
        return self.__dict__[key]

    def get(self, key, default=None):
        try:
            return self.__dict__[key]
        except KeyError:
            return default


class Settings(IndexableNamespace):
    db = None
    _cached_standby_committee = None
    default_settings = {
        'network': {
            'magic': 5195086,
            'seedlist': [],
            'validators_count': 1,
            'standby_committee': ['02158c4a4810fa2a6a12f7d33d835680429e1a68ae61161c5b3fbc98c7f1f17765']
        },
        'storage': {
            'use_default': True,
            'default_provider': 'memory',
            "providers": {
                "memory": {
                    'class_path': 'neo3.storage.implementations.MemoryDB',
                    'options': {}
                },
                "leveldb": {
                    'class_path': 'neo3.storage.implementations.LevelDB',
                    'options': {
                        'path': '/tmp/neo3/'
                    }
                },
                "postgresql": {
                    'class_path': 'neo3.storage.implementations.PostgresDB',
                    'options': {
                        'host': '127.0.0.1',
                        'port': 5432
                    }
                }
            }
        },
        'native_contract_activation': {}
    }

    @classmethod
    def from_json(cls, json: dict):
        o = cls(**json)
        o._convert(o.__dict__, o.__dict__)
        return o

    @classmethod
    def from_file(cls, path_to_json: str):
        with open(path_to_json, 'r') as f:
            data = json.load(f)
        return cls.from_json(data)

    def register(self, json: dict):
        self.__dict__.update(json)
        self._convert(self.__dict__, self.__dict__)

    def _convert(self, what: dict, where: dict):
        # turn all _dictionary what into IndexableNamespaces
        to_update = []
        for k, v in what.items():
            if isinstance(v, dict):
                to_update.append((k, IndexableNamespace(**v)))

        for k, v in to_update:
            if isinstance(where, dict):
                where.update({k: v})
            else:
                where.__dict__.update({k: v})
            self._convert(where[k].__dict__, where[k].__dict__)

    @property
    def standby_committee(self) -> List[cryptography.ECPoint]:
        if self._cached_standby_committee is None:
            points = []
            for p in self.network.standby_committee:
                points.append(cryptography.ECPoint.deserialize_from_bytes(binascii.unhexlify(p)))
            self._cached_standby_committee = points
        return self._cached_standby_committee

    @property
    def standby_validators(self) -> List[cryptography.ECPoint]:
        return self.standby_committee[:self.network.validators_count]

    @property
    def database(self):
        try:
            if self.db:
                return self.db

            if not self.storage.use_default:
                return None

            default_provider_name = self.storage.default_provider
            provider = self.storage.providers[default_provider_name]
            db_class = load_class_from_path(provider.class_path)
            return db_class(provider.options.__dict__)
        except Exception as e:
            return None

    def reset_settings_to_default(self):
        self.__dict__.clear()
        self.__dict__.update(self.from_json(self.default_settings).__dict__)


settings = Settings.from_json(Settings.default_settings)
