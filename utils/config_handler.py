import json
import os
from typing import Any

DEFAULT_CONFIG = """
{
    "clientpool_config": {
        "proxy": {
            "enable": true,
            "url": ""
        },
        "max_connections": 3,
        "request_interval": 2,
        "primary_account": {
            "id": 0,
            "email": "",
            "cookies": {"PHPSESSID": ""}
        },
        "client_pool": []
    },
    "logger_config": {
        "version": 1,
        "disable_existing_loggers": false,
        "formatters": {
            "standard": {
                "format": "%(asctime)s [%(levelname)s] - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "detailed": {
                "format": "%(asctime)s [%(levelname)s] - %(name)s - %(pathname)s:%(lineno)d - [%(funcName)s] - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "standard",
                "stream": "ext://sys.stdout"
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "detailed",
                "filename": "crawler.log",
                "maxBytes": 1048576,
                "backupCount": 5,
                "encoding": "utf8"
            }
        },
        "loggers": {
            "crawler": {
                "level": "DEBUG",
                "handlers": ["console", "file"],
                "propagate": "no"
            },
            "httpx": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": "no"
            },
            "httpcore": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": "no"
            }
        },
        "root": {"level": "WARNING", "handlers": []}
    }
}
"""


class ConfigHandler:
    def __init__(self, config_file_path: str) -> None:
        self.path = config_file_path
        if os.path.exists(config_file_path):
            self._config = self._load()
        else:
            self._config = json.loads(DEFAULT_CONFIG)
            self.save()

    def _load(self) -> dict:
        with open(self.path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config

    def get(self, path: str, default=None) -> Any:
        keys = path.split(".")
        data = self._config.copy()
        for k in keys:
            if not isinstance(data, dict):
                return default
            data = data.get(k)
            if data is None:
                return default
        return data

    def require(self, path: str) -> Any:
        keys = path.split(".")
        data = self._config.copy()
        for k in keys:
            if not isinstance(data, dict):
                raise KeyError(f"Config path '{k}' invalid")
            if k not in data:
                raise KeyError(f"Config key '{k}' not found")

            data = data[k]
        return data

    def update(self, path: str, value: Any) -> None:
        """
        Only update existing values.
        Adding new key-value pairs is not allowed.
        """
        keys = path.split(".")
        data = self._config
        for k in keys[:-1]:
            if not isinstance(data, dict):
                raise KeyError(f"Config path '{k}' invalid")
            if k not in data:
                raise KeyError(f"Config key '{k}' not found")
            data = data[k]
        key = keys.pop()
        if key not in data:
            raise KeyError(f"Config key '{key}' not found")
        data[key] = value
        self.save()

    def save(self) -> None:
        try:
            tmp = self.path + ".tmp"

            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=4)

            os.replace(tmp, self.path)
        except Exception:
            raise RuntimeError("Save config failed")
