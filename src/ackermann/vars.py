""" Config variables

This is just a wrapper around `contextvars.ContextVar` with added features.

The idea here is that it sometimes is quite hard to keep track of config settings
and the like. By defining a config variable you can always import the correct variable
with the added bonus of documenting all variables in scope.
"""

import inspect
import re
import traceback
from typing import Dict

from .config import get_config

_match_assignment = re.compile(r"^\s*([^\W0-9]\w*)\s*=")


class ConfigVar:
    """ConfigVar class

        :ivar name: The name of this variable as it should be used in configs
        :ivar description: A short description of what this variable does
        :ivar format: A format specification (this doesn't do anything yet)
        :ivar type: The type this variable excepts (this doesn't do anything yet)
        :ivar default: A default value, if not set trying to get this variable will raise an
            exception
        :ivar module_path: Tries to store the module path and the name this variable is safed in.
        :ivar source: File where this ConfigVar is defined.
    """
    _variables: Dict[str, "ConfigVar"] = {}

    # pylint: disable=redefined-builtin
    def __init__(self, name, description=None, format=None, type=None, **kwargs):
        """Creates a configvar

        If you want to pass a default value you must use keyword arguments.
        Just like `contextvars.ContextVar`.
        """

        if name in self._variables:
            raise Exception("Config Var {} is already defined".format(name))
        self._variables[name] = self

        self.name = name
        self.description = description
        caller_stack = traceback.extract_stack(limit=2)[0]

        module_path = inspect.getmodule(None, _filename=caller_stack[0])
        if module_path is not None:
            match = _match_assignment.match(caller_stack.line)
            if match:
                var_name = match.group(1)
                self.module_path = "{}:{}".format(module_path.__name__, var_name)
            else:
                var_name = None
                self.module_path = "{}".format(module_path.__name__)
        else:
            self.module_path = None
        self.source = "{}:{}".format(caller_stack.filename, caller_stack.lineno)

        self.format = format
        self.type = type

        if "default" in kwargs:
            self.default = kwargs["default"]

    def get(self, config=None):
        """Return the current value of this variable

        :param config: If you already got a config you can pass it to get the
            value from the config.
        """
        if config is None:
            config = get_config()

        try:
            return config[self.name]
        except KeyError:
            try:
                return self.default
            except AttributeError:
                pass
        raise LookupError(
            "Config Var {} is not set and has no default value".format(self.name)
        )

    def set(self, value, config=None):
        """Set the value of the Variable

        :param config: If you already got a config you can pass it to set the value in that config.
        """
        if config is None:
            config = get_config()
        config[self.name] = value

    @classmethod
    def print_variables(cls):
        """Prints all registered variables and their infos"""
        for name, var in cls._variables.items():
            print("{}".format(name))
            print("Source:      {}".format(var.source))
            print("Module:      {}".format(var.module_path))
            print("Type:        {}".format(var.type))
            print("Format:      {}".format(var.format))
            try:
                print("Value:       {}".format(var.get()))
            except LookupError:
                pass

            try:
                print("Default:     {}".format(var.default))
            except AttributeError:
                pass

            if var.description is not None:
                print("Description: {}".format(var.description))
            print()
