"""Units for logging"""
import logging

from ..config import config_unit
from .config import init_arg_subparser, parse_config
from .vars import config_verbose


def _get_log_level(level):
    """Return a log leve base on number of -v's"""
    levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    level = levels[min(len(levels)-1, level)]
    return level


@config_unit(after=parse_config, before=init_arg_subparser)
def set_log_level(config):
    """Set log level using the `-vvv` option"""
    logging.basicConfig(level=_get_log_level(config_verbose.get(config)))
