"""Config units that parse config files"""
from ..config import config_unit
from .argparse import init_arg_parser, init_arg_subparser
from .vars import config_config


@config_unit(depends=init_arg_parser, after=init_arg_parser, before=init_arg_subparser)
def parse_config(config):
    """Parse a config module/file"""
    if config_config.get(config) is not None:
        config.load_from_module_path(config_config.get(config))
