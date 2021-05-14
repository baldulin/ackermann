"""Ackermann command interface

Use this to easily add a command to your project, using the default targets,
or custom targets you implemented.
"""


from argparse import ArgumentParser
from typing import Dict, List, Optional

from .config import Config, ConfigUnit


class MetaCommand(type):
    """Metaclass for command

    Collects all commands in the :attr:`commands`

    :cvar: commands A dict with all the imported commands
    """
    commands: Dict[str, "Command"] = {}

    def __init__(cls, name, bases, dct):
        try:
            if dct["name"] is None:
                return

            MetaCommand.commands[dct["name"]] = cls
        except KeyError as exc:
            raise AttributeError("Command needs a name attribute") from exc
        super().__init__(name, bases, dct)

    @classmethod
    def get_help_text(cls):
        """Print the help text for argparser"""
        help_text = "Enter one of the following commands:"

        max_name_length = max(len(c) for c in cls.commands)
        for name, command in cls.commands.items():
            help_text += "\n\t{:<{l}} {}".format(name, command.short_description, l=max_name_length)

        return help_text


class Command(metaclass=MetaCommand):
    """Represents a command

    :ivar name: The short name of the command (if None this command can't be called)
    :ivar short_description: The description used in help
    :ivar targets: The config targets that have to be executed before running this
        command.
    :ivar is_async: Run this command async if set `True` (i.e. run :attr:`async_run`)
    :ivar trigger_startup_signals: Run triggers ready, and stopping automatically if set to `True`
    """

    name: Optional[str] = None
    short_description: Optional[str] = ""
    targets: List[ConfigUnit] = []
    is_async: bool = False
    trigger_startup_signals: bool = True

    def run(self, config: Config) -> None:
        """Run this non-async after initializing the config
        """
        raise NotImplementedError()

    async def async_run(self, config: Config) -> None:
        """Run this function async after initializing the config
        """
        raise NotImplementedError()

    @classmethod
    def get_arguments(cls, parser: ArgumentParser) -> ArgumentParser:
        """Adds new arguments to the argparser
        """
        return parser
