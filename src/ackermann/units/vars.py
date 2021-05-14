"""All config vars as used by the default units"""


from argparse import ArgumentParser

from ..vars import ConfigVar

config_args = ConfigVar(
    "ARGS",
    "Argument parsers result",
    default=None,
)

config_verbose = ConfigVar(
    "VERBOSE",
    "Verbosity level",
    default=None,
    type=int,
)

config_config = ConfigVar(
    "CONFIG",
    "Config file to parse",
    default=None,
    type=str,
)

config_arg_parser = ConfigVar(
    "ARG_PARSER",
    "The argument parser",
    default=None,
    type=ArgumentParser,
)

config_arg_command_parser = ConfigVar(
    "ARG_COMMAND_PARSER",
    "Subparser for the command",
    default=None,
    type=ArgumentParser,
)

config_systemd_logging = ConfigVar(
    "SYSTEMD_LOGGING",
    "Enable or disable systemd logging",
    default=False,
    type=bool,
)

config_systemd_notify = ConfigVar(
    "SYSTEMD_NOTIFY",
    "If systemd should be informed of startup",
    default=False,
    type=bool,
)

config_processes = ConfigVar(
    "NUMBER_OF_PROCESSES",
    "Number of processes to be forked",
    default=1,
    type=int,
)
