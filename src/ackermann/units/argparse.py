""" Config units that parse command line arguments"""

from argparse import ArgumentParser

from ..command import MetaCommand
from ..config import config_unit
from ..exceptions import StopInitException
from ..logger import logger
from .vars import (config_arg_command_parser, config_arg_parser, config_args,
                   config_config, config_verbose)


@config_unit
def init_arg_parser(config):
    """Prepare basic argparser
    """
    parser = ArgumentParser(prog=config.get("PROJECT_NAME", "TODO"), add_help=False)
    parser.add_argument(
        "-h",
        "--help",
        action="store_true",
        help="show this help message and exit",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="raise log level",
    )
    parser.add_argument(
        "-V",
        "--vars",
        action="store_true",
        help="show all config variables",
    )
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="Which targets should run",
    )
    parser.add_argument(
        "--blacklist-target",
        action="append",
        default=[],
        help="Blacklist this target",
    )
    parser.add_argument(
        "--disable-target",
        action="append",
        default=[],
        help="Disable this target",
    )

    parser.add_argument(
        '-c',
        '--config',
        help='Config file'
    )

    known_args, _ = parser.parse_known_args()

    # Store known args for help
    config_args.set(known_args, config)
    config_verbose.set(known_args.verbose, config)
    config_config.set(known_args.config, config)

    if known_args.config:
        # pylint: disable=import-outside-toplevel
        from .config import parse_config
        config.add_target(parse_config)

    config_arg_parser.set(parser, config)

    subparsers = parser.add_subparsers(
        required=True,
        dest="command",
        title="Command",
        description="Which command to run",
        help="",
    )
    config_arg_command_parser.set(subparsers, config)


@config_unit(depends=init_arg_parser, after=init_arg_parser)
def init_arg_subparser(config):
    """Prepare argparsers for commands
    """
    subparsers = config_arg_command_parser.get(config)
    for name, command in MetaCommand.commands.items():
        logger.debug("Adds Command %s", name)
        subparser = subparsers.add_parser(name, help=command.short_description)
        command.get_arguments(subparser)


@config_unit(depends=init_arg_parser, after=[init_arg_subparser, init_arg_parser])
def parse_parameters(config):
    """Parse all parameters including command parameters
    """
    arg_parser = config_arg_parser.get(config)
    args = arg_parser.parse_args()
    config_args.set(args, config)

    if args.help:
        arg_parser.print_help()
        raise StopInitException()
