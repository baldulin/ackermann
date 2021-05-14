"""Base units for multiprocessing and asyncio"""


import asyncio
from multiprocessing import Process
from typing import Any, Generator

from ..config import Config, ConfigUnit, async_run, config_unit, run
from ..logger import logger
from .vars import config_processes

ASYNC_UNIT = ConfigUnit(
    name="ASYNC_UNIT",
    description="Base unit for asyncio event loops setups",
    exclusive=True,
)


# pylint: disable=unused-argument
@config_unit(belongs=ASYNC_UNIT)
def async_event_loop(config: Config) -> Generator[Any, Any, Any]:
    """Returns default asyncio event loop"""

    def wrapped(config: Config):
        event_loop = asyncio.get_event_loop()
        event_loop.run_until_complete(async_run(config=config.subconfig()))
    yield wrapped


MULTIPROCESSING_UNIT = ConfigUnit(
    name="MULTIPROCESSING_UNIT",
    description="Base unit for multiprocessing setups",
    before=ASYNC_UNIT,
    exclusive=True,
)


@config_unit(belongs=MULTIPROCESSING_UNIT)
def multiprocessing_unit(config: Config):
    """Returns default multiprocessing creator"""
    processes_count = config_processes.get(config)
    if processes_count <= 1:
        yield
        return

    def wrapped(config: Config):
        processes = []
        for i in range(processes_count):
            process = Process(target=run, args=(None, config.subconfig(), None))
            process.start()
            logger.info("Spawned Process %s:%s", i, process)
            processes.append(process)

        for process in processes:
            logger.info("Joins Process %s:%s", i, process)
            try:
                process.join()
            except KeyboardInterrupt:
                logger.info("Received Keyboard Interrupt")
            logger.info("Joined Process %i:%s", i, process)
    yield wrapped
