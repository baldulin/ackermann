"""Units to run commands"""
from ..command import MetaCommand
from ..config import config_unit
from .argparse import init_arg_subparser, parse_parameters
from .config import parse_config
from .logging import set_log_level
from .systemd import systemd_logging_integration, systemd_notify_integration
from .vars import ConfigVar, config_args


@config_unit(
    depends=[
        parse_parameters,
        init_arg_subparser,
        set_log_level,
        systemd_notify_integration,
        systemd_logging_integration,
    ],
    after=[
        set_log_level,
        parse_config,
        parse_parameters,
        init_arg_subparser,
    ]
)
def run_command(config):
    """Run a command"""
    args = config_args.get(config)
    command_cls = MetaCommand.commands[args.command]
    command = command_cls()
    config.add_targets(command.targets)

    if args.vars:
        # Just show the settings with which this command is run
        # pylint: disable=unused-argument
        def wrapper(config):
            ConfigVar.print_variables()
        config.set_func(wrapper)
    else:
        config.set_func(command)
