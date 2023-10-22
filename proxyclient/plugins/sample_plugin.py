from typing import Any, Callable, Optional
from plugins import Plugin, PluginManager

class SamplePlugin(Plugin):
    def __init__(self) -> None:
        super().__init__()
        print("Created a SamplePlugin object")

    def name(self) -> str:
        return "sample_plugin"
    
    def command(self) -> str:
        return "sample"
    
    def fn(self) -> Callable[..., Any]:
        return sample_fn

def sample_fn(self, dummy: int, opt: Optional[str] = None):
    """sample function to demonstrate the plugin manager
    :param dummy: this is a parameter
    :param opt: this is an optional parameter
    """
    print(f"sample command invoked with {dummy=} and {opt=}")

