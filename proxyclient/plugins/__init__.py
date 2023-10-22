from pathlib import Path
from typing import Callable, Dict, Optional
from m1n1.utils import Reloadable
from abc import ABC, abstractmethod

from m1n1.proxyutils import ProxyUtils
import importlib
import inspect


class Plugin(ABC):
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def command(self) -> str:
        ...

    @abstractmethod
    def install(self):
        ...

    @abstractmethod
    def fn(self) -> Callable:
        ...


class PluginManager:
    ...


class PluginManager(Reloadable):
    def __init__(
        self, proxy_utils: ProxyUtils, private_constructor_use_get_instance: int = 0
    ) -> None:
        if private_constructor_use_get_instance != 42:
            raise ValueError(
                "You must not call PluginManager() directly: use PluginManager.get_instance() instead"
            )

        super().__init__()
        self._proxy_utils = proxy_utils
        self._plugins: Dict[str, Plugin] = {}

    def load_plugins(self):
        this_file = Path(__file__)
        for file in filter(lambda f: f != this_file, this_file.parent.glob("*.py")):
            print(file)
            if this_file.parent == file.parent:
                package = file.parent.stem
            else:
                raise NotImplementedError("Not implemented yet")
            print(f"Will import {file.stem} from package {package}")
            mod = importlib.import_module(f"{package}.{file.stem}")
            for class_name, clazz in inspect.getmembers(mod, inspect.isclass):
                if class_name == Plugin.__name__:
                    continue
                print(class_name, clazz)
                if issubclass(clazz, Plugin):
                    instance: Plugin = clazz()
                    print(
                        f"Loading plugin {instance.name()} from class {class_name}: {instance=}"
                    )
                    instance.install()

        print(f"{len(self._plugins)} new plugins installed")
        for name, plugin in self._plugins.items():
            print(f"\t{name}: command {plugin.command()} {plugin.fn().__doc__}")

    def add(self, plugin: Plugin):
        self._plugins[plugin.name()] = plugin
        self.insert_method_in_proxy_util(plugin.command(), plugin.fn())

    def insert_method_in_proxy_util(self, name: str, method: Callable):
        # print(f"Adding function {name} to {self._proxy_utils}")
        setattr(type(self._proxy_utils), name, method)

    @classmethod
    def get_instance(cls, proxy_utils: Optional[ProxyUtils] = None) -> PluginManager:
        global _INSTANCE
        if _INSTANCE is None:
            if proxy_utils is None:
                print(" Raise")
                raise ValueError(
                    "proxy_utils argument is mandatory for the first call of get_instance"
                )
            else:
                _INSTANCE = PluginManager(
                    proxy_utils, private_constructor_use_get_instance=42
                )

        return _INSTANCE

    def _reloadme(self):
        global _INSTANCE
        _INSTANCE = None
        return super()._reloadme()


_INSTANCE: Optional[PluginManager] = None


if "__main__" == __name__:
    try:
        pm = PluginManager()
        raise Exception("The fail safe on direct contructor call failed: ;(")
    except ValueError as e:
        print("OK, direct constructor call failed as expected")
    pm = PluginManager.get_instance()
