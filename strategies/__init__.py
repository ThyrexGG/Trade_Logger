import os
import importlib
import inspect
from .base import BaseStrategy

# A central registry of all available strategies
STRATEGY_REGISTRY = {}

def load_strategies():
    """
    Dynamically loads all strategy modules from this directory and registers them.
    """
    current_dir = os.path.dirname(__file__)
    for filename in os.listdir(current_dir):
        if filename.endswith(".py") and filename not in ["__init__.py", "base.py"]:
            module_name = f"strategies.{filename[:-3]}"
            module = importlib.import_module(module_name)
            
            # Find all classes in the module that subclass BaseStrategy
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseStrategy) and obj is not BaseStrategy:
                    # Instantiate and register the strategy by its human-readable name
                    strategy_instance = obj()
                    STRATEGY_REGISTRY[strategy_instance.name] = strategy_instance

# Load all strategies when the module is imported
load_strategies()

def get_strategy(name: str) -> BaseStrategy:
    """Returns a strategy instance by name."""
    return STRATEGY_REGISTRY.get(name)

def get_all_strategy_names() -> list:
    """Returns a list of all registered strategy names."""
    return list(STRATEGY_REGISTRY.keys())
