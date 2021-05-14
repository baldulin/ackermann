"""Systemd targets"""
import logging

from ..config import config_unit
from ..logger import logger
from .argparse import init_arg_parser
from .config import parse_config
from .logging import _get_log_level, set_log_level
from .vars import config_systemd_logging, config_systemd_notify, config_verbose


@config_unit(after=[init_arg_parser, parse_config, set_log_level])
def systemd_logging_integration(config):
    """Enable the systemd logger"""
    if not config_systemd_logging.get(config):
        return

    # pylint: disable=import-outside-toplevel
    from systemd.journal import JournalHandler

    journald_handler = JournalHandler()
    root_logger = logging.root
    # Replace root logger with systemd logger
    root_logger.removeHandler(root_logger.handlers[0])
    root_logger.addHandler(journald_handler)
    root_logger.setLevel(_get_log_level(config_verbose.get(config)))

    logger.info("Enabled systemd logging")


@config_unit(after=[init_arg_parser, parse_config, set_log_level])
def systemd_notify_integration(config):
    """Enable systemd notifications"""
    if not config_systemd_notify.get(config):
        return

    # pylint: disable=import-outside-toplevel
    from systemd.daemon import notify

    # pylint: disable=unused-argument
    def systemd_notify(config, signal):
        if signal == "ready":
            notify("READY=1")
        elif signal == "reloading":
            notify("RELOADING=1")
        elif signal == "stopping":
            notify("STOPPING=1")

    config.add_signal_handler("ready", systemd_notify)
    config.add_signal_handler("reloading", systemd_notify)
    config.add_signal_handler("stopping", systemd_notify)
