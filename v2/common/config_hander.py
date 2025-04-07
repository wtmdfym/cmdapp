import json
import os


class ConfigHander:
    def __init__(self, config_file_path: str, default_config_save_path: str) -> None:
        if os.path.exists(config_file_path):
            self.path = config_file_path
        else:
            self.path = default_config_save_path
        self.__config = self.__load_config()

    def __load_config(self) -> dict:
        with open(self.path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config

    def get_config(self, key: str):
        return self.__config.get(key)

    def require_config(self, key: str):
        return self.__config[key]

    def update_config(self, key: str, value) -> None:
        self.__config[key] = value

    def save_config(self) -> bool:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.__config, f, ensure_ascii=False, indent=4)
            return True
        except Exception:
            return False
