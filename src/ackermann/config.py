"""Configuration abstraction

This is pretty much based on systemd units and typical hook implementations.

The only weird part is the the async context need's to be configureable. So in that instant
a function needs to take over return the async event loop. And the config will then run in that
loop.
Because we use generator's we might return certain values. To do so.
"""
from collections import defaultdict
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from inspect import (isasyncgenfunction, iscoroutinefunction,
                     isgeneratorfunction)
from itertools import chain
from types import ModuleType
from typing import (Any, AsyncGenerator, Callable, Coroutine, Dict, Generator,
                    List, Optional, Union)

from .exceptions import StopInitException
from .kahn import KahnIterator
from .logger import logger

CurrentConfig: ContextVar[Optional["Config"]] = ContextVar("Config", default=None)
SignalType = Union[
    Callable[["Config", str], Coroutine[Any, Any, None]],
    Callable[["Config", str], None]
]
FinalTargetType = Any


# pylint: disable=too-few-public-methods
class ConfigUnitListener:
    """Interface to listen to new ConfigUnits beeing created"""
    def add_target(self, target: "ConfigUnit", force: bool = True) -> None:
        """A new config unit was created"""
        raise NotImplementedError()


# pylint: disable=too-many-instance-attributes, too-many-public-methods
class Config(ConfigUnitListener):
    """Represents a config and a group of startup targets

    This is the main entrypoint for ackermann. Here your can register
    all targets to be run and the command/function to be executed.

    :ivar func: Stores the function to be run after initialization
    :ivar targets: All targets that need to be run
    :ivar blacklist_targets: Targets that should not be run
    :ivar variables: A dict storing all variables
    :ivar ran_units: All units that ran already
    :ivar active_units: All units that ran and need cleanup
    :ivar signals: A dict containing signals and handlers for these signals
    :ivar entry_point: The unit that spawned this object
    """

    def __init__(
            self,
            func=None,
            variables: Optional[Dict[str, Any]] = None,
            targets: Optional[List["ConfigUnit"]] = None
    ):
        """Initializes the config

        :param func: A function to be executed after initialization
        :param variables: A set of variables
        :param targets: The targets to be run
        """
        self.func = func
        self.targets: List["ConfigUnit"] = []
        self.blacklisted_targets: List["ConfigUnit"] = []
        assert self.func is not None or self.targets is not None

        self.variables: Dict[str, Any] = variables if variables is not None else dict()
        self.unit_iterator = KahnIterator([])
        self.ran_units: List["ConfigUnit"] = []
        self.active_units: Dict["ConfigUnit", Any] = {}

        if targets is not None:
            for target in targets:
                self.add_target(target)
        self.entry_point = None

        self.signals: Dict[str, List[SignalType]] = defaultdict(list)
        ConfigUnit.add_listener(self)

    def add_signal_handler(self, signal: str, handler: SignalType) -> None:
        """Add a signal handler for a given signal

        :param signal: The signal to be used
        :param handler: The handler function might be a coroutine aswell
        """
        self.signals[signal].append(handler)

    def remove_signal_handler(self, signal: str, handler: SignalType) -> None:
        """Remove a signal handler for a given signal

        :param signal: The signal to be used
        :param handler: The handler to be removed
        """
        self.signals[signal].remove(handler)

    def trigger_signal(self, signal: str) -> None:
        """Trigger the execution of a signal

        :param signal: The signal to be triggered
        """
        logger.debug("Triggered Signal %s", signal)
        for handler in self.signals[signal]:
            if not iscoroutinefunction(handler):
                handler(self, signal)

    def trigger_ready(self) -> None:
        """Trigger the ready signal"""
        self.trigger_signal("ready")

    def trigger_reloading(self) -> None:
        """Trigger the reloading signal"""
        self.trigger_signal("reloading")

    def trigger_stopping(self) -> None:
        """Trigger the stopping signal"""
        self.trigger_signal("stopping")

    async def async_trigger_signal(self, signal: str, call_non_async: bool = True) -> None:
        """Asynchronously trigger a signal

        :param signal: The signal to be triggered
        :param call_non_async: If all non async handlers should be triggered aswell
        """
        logger.debug("Triggered async Signal %s", signal)
        for handler in self.signals[signal]:
            if iscoroutinefunction(handler):
                await handler(self, signal)
            elif call_non_async:
                handler(self, signal)

    async def async_trigger_ready(self) -> None:
        """Asynchronously trigger ready signal"""
        await self.async_trigger_signal("ready")

    async def async_trigger_reloading(self) -> None:
        """Asynchronously trigger reloading signal"""
        await self.async_trigger_signal("reloading")

    async def async_trigger_stopping(self) -> None:
        """Asynchronously trigger stopping signal"""
        await self.async_trigger_signal("stopping")

    def subconfig(self) -> "Config":
        """Return a subconfig

        This is used if a unit wants to spawns multiple processes,
        or turns over the execution into an async event loop
        """
        config = Config()
        config.func = self.func
        config.targets = self.targets.copy()
        config.blacklisted_targets = self.blacklisted_targets.copy()
        config.variables = self.variables.copy()
        config.unit_iterator = self.unit_iterator.copy()
        config.ran_units = self.ran_units.copy()
        config.active_units = self.active_units.copy()
        config.entry_point = self.unit_iterator.lst[-1]
        config.signals = self.signals.copy()
        return config

    # pylint: disable=inconsistent-return-statements
    def init(self) -> Optional[FinalTargetType]:
        """Execute the initialization and run all targets/commands"""
        for unit in self.unit_iterator:
            logger.debug("Init Config Unit %s", unit)

            if unit in self.blacklisted_targets:
                logger.debug("Config Unit %s is blacklisted", unit)
                instance = None
                result = None
            else:
                try:
                    if unit.is_empty:
                        instance = None
                        result = None
                    elif unit.is_generator:
                        instance = unit(self)
                        result = next(instance)
                    else:
                        instance = None
                        result = unit(self)
                except StopInitException:
                    logger.debug("Ran Config Unit %s it stopped the init", unit)
                    self.func = None
                    return None

            self.active_units[unit] = instance
            self.ran_units.append(unit)

            if result is not None:
                logger.debug("Inited Config Unit %s returned %s", unit, result)
                return result
            logger.debug("Inited Config Unit %s", unit)
        return None

    def exit(self) -> None:
        """Exit all targets"""
        while True:
            try:
                unit = self.ran_units.pop()
            except IndexError:
                break

            instance = self.active_units[unit]

            if unit == self.entry_point:
                return

            logger.debug("Exit Config Unit %s", unit)
            if not (unit.is_empty or instance is None):
                try:
                    next(instance)
                except StopIteration:
                    pass
            del self.active_units[unit]
            logger.debug("Exited Config Unit %s", unit)


    # pylint: disable=too-many-nested-blocks, too-many-branches
    async def async_init(self) -> Optional[FinalTargetType]:
        """Asynchronously execute all targets/commands"""
        for unit in self.unit_iterator:
            logger.debug("Run Config Unit %s", unit)
            if unit in self.ran_units:
                logger.debug("Unit already ran %s", unit)
                continue

            if unit.is_empty:
                instance = None
                result = None
            else:
                if unit in self.blacklisted_targets:
                    logger.debug("Config Unit %s is blacklisted", unit)
                    instance = None
                    result = None
                else:
                    try:
                        if unit.is_generator:
                            instance = unit(self)
                            if unit.is_async:
                                logger.debug("Generate Async")
                                result = await instance.__anext__()
                            else:
                                result = next(instance)
                        else:
                            instance = None
                            if unit.is_async:
                                logger.debug("Run Async")
                                result = await unit(self)
                            else:
                                result = unit(self)
                    except StopInitException:
                        logger.debug("Ran Config Unit %s it stopped the init", unit)
                        self.func = None
                        return None

            self.active_units[unit] = instance
            self.ran_units.append(unit)

            if result is not None:
                logger.debug("Ran Config Unit %s returned %s", unit, result)
                return result
            logger.debug("Inited Config Unit %s", unit)
        return None

    async def async_exit(self) -> None:
        """Asynchronously exit all targets"""
        while True:
            try:
                unit = self.ran_units.pop()
            except IndexError:
                break
            instance = self.active_units[unit]

            if unit == self.entry_point:
                return

            logger.debug("Exit Config Unit %s", unit)
            if not (unit.is_empty or instance is None):
                try:
                    if unit.is_async:
                        await instance.__anext__()
                    else:
                        next(instance)
                except (StopIteration, StopAsyncIteration):
                    pass
            del self.active_units[unit]
            logger.debug("Exited Config Unit %s", unit)

    def blacklist_target(self, target: "ConfigUnit"):
        """Blacklist a target

        :param target: The target to blacklist
        """
        self.blacklisted_targets.append(target)

        for unit in target.contains:
            self.blacklisted_targets.append(unit)

    def __getitem__(self, key: str) -> Any:
        """Returns a config value

        :param key: The key under which the value is stored
        """
        return self.variables[key]

    def get(self, key: str, default: Any = None) -> Any:
        """Returns a config value with a given default
        :param key: The key to return
        :param default: The default to return in the case the key is not set
        """
        try:
            return self.variables[key]
        except KeyError:
            return default

    def has(self, key: str) -> Any:
        """Check if key is in the config

        :param key: The key to check for
        """
        return key in self.variables

    __contains__ = has

    def __setitem__(self, key: str, value: Any) -> None:
        """Set a config value

        :param key: The key to set
        :param value: The value to use
        """
        self.variables[key] = value

    def __delitem__(self, key: str) -> None:
        """Remove a config value

        :param key: The key to remove
        """
        del self.variables[key]

    def __len__(self) -> int:
        """Return the number of variables set"""
        return len(self.variables)

    def add_target(self, target: "ConfigUnit", force: bool = True) -> None:
        """Add a target

        :param target: The target to be added
        :param force: if set (default) than this target will always be executed.
            Otherwise it will be checked if this target or its group is already selected
            to be run
        """
        if target in self.targets:
            return
        if target in self.blacklisted_targets:
            return
        logger.debug("Add target %s", target)

        if force or any(container in self.targets for container in target.belongs):
            self.targets.append(target)
            self.unit_iterator.add_node(target)

            for dependency in chain(target.depends, target.contains):
                self.add_target(dependency, force=force)

            for container in target.belongs:
                if container.exclusive is True:
                    for other_unit in container.contains:
                        if other_unit != target:
                            self.unit_iterator.remove_node(other_unit)
                            self.blacklist_target(other_unit)

    def add_targets(self, targets: List["ConfigUnit"]) -> None:
        """Add a couple of targets

        :param targets: A list of targets to be added
        """
        for target in targets:
            self.add_target(target)

    def set_func(self, func: FinalTargetType) -> None:
        """Set a function/command to be executed

        :param func: A function/command, might be a coroutine aswell
        :raises Exception: If a function/command is set already
        """
        if self.func is not None:
            raise Exception("Can't change func")

        self.func = func

        # pylint: disable=import-outside-toplevel
        from .command import Command
        if iscoroutinefunction(func) or (isinstance(func, Command) and func.is_async):
            # pylint: disable=import-outside-toplevel
            from .units import ASYNC_UNIT
            self.add_target(ASYNC_UNIT)

    def load_from_module_path(self, filename: str) -> None:
        """Load config from python modules

        :param filename: A filename to load config values from
        """
        # pylint: disable=import-outside-toplevel
        import importlib.util
        spec = importlib.util.spec_from_file_location("base_config", filename)
        module = importlib.util.module_from_spec(spec)
        if spec.loader is not None:
            spec.loader.exec_module(module)
        else:
            raise Exception("Could not get module loader from spec")
        self.load_from_module(module)

    def load_from_module(self, module: ModuleType) -> None:
        """Updates variables from module variables

        Fetches all keys from a module not beginning with `__` and
        puts them into the variables dict.

        :param module: The Module to load from
        """
        for key in dir(module):
            if key.startswith("__") and key.endswith("__"):
                continue
            value = getattr(module, key)
            self[key] = value

    @classmethod
    def get_from_module(cls, module: ModuleType) -> "Config":
        """Get a config object with a preset of values from a module

        :param module: The module to be used to initialize the values
        """
        config = Config()
        config.load_from_module(module)
        return config


def get_config() -> Optional[Config]:
    """Returns the current config variable"""
    return CurrentConfig.get()


def set_config(config: Config):
    """Sets the current config variable"""
    CurrentConfig.set(config)


OptionalConfigUnitList = Optional[Union["ConfigUnit", List["ConfigUnit"]]]


def _param_to_list(param: OptionalConfigUnitList) -> List["ConfigUnit"]:
    """Returns a list of items

    If param is a list returns param,  if param is None returns empty list otherwise
    return a list containing param.
    """
    if param is None:
        return []
    if isinstance(param, list):
        return param.copy()
    return [param]


class ConfigUnit:
    """Represents a config step

    This might do something or just be used to indicate a certain part of initialization.

    :ivar name: A name for this unit
    :ivar description: A short description of what this unit does
    :ivar contains: What config_units are contained in this unit, this means other units that point
        to this one
    :ivar belongs: To what config_unit this unit belongs to
    :ivar depends: What config units **must** be run for this unit to run successfully
        Note that this does not mean that the unit needs to be run *after* or *before*. It just
        means that the unit needs to be run at some point.
    :ivar after: Run these units after this unit
    :ivar before: Run these units before this unit
    :ivar conflicts: Never run any of these units together with this unit (i.e. opposite of depends)
    :ivar func: A callable that might take over the initialization (see `ASYNC_UNIT` for instance)
    :ivar exclusive: Just run one target of the group
        (meaning just one unit that belongs to this one)
    """
    units: Dict[str, "ConfigUnit"] = {}
    listener: List[ConfigUnitListener] = []

    # pylint: disable=too-many-arguments
    def __init__(
            self,
            name: str = None,
            description: str = None,
            contains: OptionalConfigUnitList = None,
            belongs: OptionalConfigUnitList = None,
            depends: OptionalConfigUnitList = None,
            before: OptionalConfigUnitList = None,
            after: OptionalConfigUnitList = None,
            conflicts: OptionalConfigUnitList = None,
            exclusive: bool = False,
            func: Callable = None,
    ):

        self.name = name
        self.description = description
        self.contains = _param_to_list(contains)
        self.belongs = _param_to_list(belongs)
        self.depends = _param_to_list(depends)
        self.before = _param_to_list(before)
        self.after = _param_to_list(after)
        self.conflicts = _param_to_list(conflicts)
        self.exclusive = exclusive

        self.func = func
        # Figure out what func is, yeah there is a lot
        if func is None:
            self.is_async = False
            self.is_generator = False
        elif isasyncgenfunction(func):
            self.is_async = True
            self.is_generator = True
        elif iscoroutinefunction(func):
            self.is_async = True
            self.is_generator = False
        elif isgeneratorfunction(func):
            self.is_async = False
            self.is_generator = True
        else:
            self.is_async = False
            self.is_generator = False

        if self.is_async:
            # pylint: disable=import-outside-toplevel
            from .units import ASYNC_UNIT
            self.depends.append(ASYNC_UNIT)
            self.after.append(ASYNC_UNIT)

    def __str__(self) -> str:
        return "ConfigUnit(name='{}')".format(self.name)

    __repr__ = __str__

    @property
    def is_empty(self) -> bool:
        """Checks if this unit doesn't do anything"""
        return self.func is None

    def __call__(self, config: Config) -> Any:
        if self.func is not None:
            return self.func(config)
        raise Exception("This config unit is not callable")

    #pylint: disable=too-many-branches
    @classmethod
    def add_unit(cls, unit: "ConfigUnit", path: str) -> None:
        """Add a config unit to the global list of config units

        :param unit: The unit to be added
        :param path: The path of that unit
        """
        if path in cls.units:
            raise Exception("Can't overwrite config unit {}".format(path))
        cls.units[path] = unit

        for listener in cls.listener:
            listener.add_target(unit, force=False)

        for container in unit.belongs:
            if unit not in container.contains:
                container.contains.append(unit)
            for before in container.before:
                unit.before.append(before)
            for after in container.after:
                unit.after.append(after)

        for other in unit.before:
            if unit not in other.after:
                other.after.append(unit)
            for contained in other.contains:
                if unit != contained and unit not in contained.after:
                    contained.after.append(unit)
                if unit != contained and contained not in unit.before:
                    unit.before.append(contained)

        for other in unit.after:
            if unit not in other.before:
                other.before.append(unit)
            for contained in other.contains:
                if unit != contained and unit not in contained.before:
                    contained.before.append(unit)
                if unit != contained and contained not in unit.after:
                    unit.after.append(contained)

        cls.units[path] = unit

    @classmethod
    def add_listener(cls, listener: ConfigUnitListener) -> None:
        """Add a listener to track for new config units

        This is used in case an import leads to new units.
        If you initiated a config than this config will add a listener here.
        Because the listeneres `add_target` method will be called with `force=False`.
        Units will just be added if they are already implicitly selected.

        :param listener: An object that implements add_target for changes"""
        cls.listener.append(listener)


def config_unit(*args, **kwargs) -> Union[ConfigUnit, Callable[[Any], ConfigUnit]]:
    """Just a shortcut for ConfigUnit

    This decorator just shortcuts ConfigUnit calls like so:

    .. code-block:: python

        @config_unit(description="test")
        def step(config):
            pass

        # is equal to
        def _step(config):
            pass

        step = ConfigUnit(description="test", name="step", func=_step)
    """

    def wrapper(func: Any) -> ConfigUnit:
        if "name" not in kwargs:
            kwargs["name"] = func.__name__
        if "description" not in kwargs:
            kwargs["description"] = func.__doc__

        path = "{}.{}".format(func.__module__, kwargs["name"])
        unit = ConfigUnit(func=func, **kwargs)
        ConfigUnit.add_unit(unit, path)
        return unit

    if len(args) == 1 and len(kwargs) == 0:
        return wrapper(args[0])
    return wrapper


# pylint: disable=too-many-branches
async def async_run(
        func: FinalTargetType = None,
        config: Optional[Config] = None,
        targets: Optional[List[ConfigUnit]] = None
) -> None:
    """Run a programm asynchronously using ackermann

    This function will run all targets, then the function and then cleanup all the mess it left.

    :param func: The function to be run
    :param config: The config to be used if empty a new config is created
    :param targets: The targets to be run
    """

    if config is None:
        assert func is not None or targets is not None
        config = Config(targets=targets, func=func)
    else:
        assert func is None and targets is None

    assert isinstance(config, Config)

    wrapper_func = await config.async_init()

    if callable(wrapper_func):
        logger.debug("Calling %s", wrapper_func)
        try:
            if iscoroutinefunction(wrapper_func):
                await wrapper_func(config)
            else:
                wrapper_func(config)
        finally:
            logger.debug("Called %s", func)
            await config.async_exit()
    elif config.func is not None:
        func = config.func
        # pylint: disable=import-outside-toplevel
        from .command import Command

        command: Optional[Command] = None
        if isinstance(func, Command):
            command = func
            func = func.async_run if func.is_async else func.run

        if command is not None and command.trigger_startup_signals:
            await config.async_trigger_ready()

        try:
            if iscoroutinefunction(func):
                await func(config)
            else:
                func(config)
        finally:
            if command is not None and command.trigger_startup_signals:
                await config.async_trigger_stopping()
            await config.async_exit()
    else:
        await config.async_exit()


@asynccontextmanager
async def async_init(
        config: Optional[Config] = None,
        targets: Optional[List[ConfigUnit]] = None
) -> AsyncGenerator[Config, None]:
    """Asynchronously initializes all targets

    This function will not run aynthing like `async_run` but rather, as a context manager,
    enable the user to execute whatever she wants.

    .. code-block:: python

        async with async_init(config=config, targets=my_targets):
            func(config)

        # Is equivalent to
        await async_run(config=config, targets=my_targets, func=func)


    :param config: The config to be used if None a new one is created
    :param targets: the targets to be run
    """
    # pylint: disable=import-outside-toplevel
    from .units import ASYNC_UNIT

    if config is None:
        assert targets is not None
        config = Config(targets=targets)
    else:
        assert targets is None

    assert isinstance(config, Config)

    set_config(config)

    config.blacklist_target(ASYNC_UNIT)

    wrapper_func = await config.async_init()

    if wrapper_func is not None:
        raise Exception("Can't call wrapper func {} on init".format(wrapper_func))

    try:
        yield config
    finally:
        await config.async_exit()


# pylint: disable=too-many-branches
def run(
        func: FinalTargetType = None,
        config: Optional[Config] = None,
        targets: Optional[List[ConfigUnit]] = None
) -> None:
    """Run a programm using ackermann

    This function will run all targets, then the function and then cleanup all the mess it left.

    **Note**: This is the main entrypoint of ackerman. Yes you might use `async_run`.
    Aswell but this function will decide if you really need an async event loop. And you
    can add different eventloops by defining them as a `config_unit`. And then add them as target.

    :param func: The function to be run
    :param config: The config to be used if empty a new config is created
    :param targets: The targets to be run
    """
    # pylint: disable=import-outside-toplevel
    from .units import ASYNC_UNIT

    if config is None:
        assert func is not None or targets is not None
        config = Config(targets=targets, func=func)
    else:
        if targets is not None:
            for target in targets:
                config.add_target(target)
        if func is not None:
            config.func = func

    assert isinstance(config, Config)

    if iscoroutinefunction(config.func):
        config.add_target(ASYNC_UNIT)

    # Set CurrentConfig
    set_config(config)
    wrapper_func = config.init()

    if callable(wrapper_func):
        logger.debug("Calling %s", wrapper_func)
        try:
            wrapper_func(config)
        finally:
            logger.debug("Called %s", wrapper_func)
            config.exit()
    elif config.func is not None:
        logger.debug("Calling Function %s", config.func)
        func = config.func

        # pylint: disable=import-outside-toplevel
        from .command import Command

        command: Optional[Command] = None
        if isinstance(func, Command):
            command = func
            func = func.async_run if func.is_async else func.run

        if command is not None and command.trigger_startup_signals:
            config.trigger_ready()

        assert not iscoroutinefunction(config.func), "Must run func in asyncio context"
        try:
            func(config)
        finally:
            if command is not None and command.trigger_startup_signals:
                config.trigger_stopping()
            config.exit()
    else:
        config.exit()


@contextmanager
def init(
        config: Optional[Config] = None,
        targets: Optional[List[ConfigUnit]] = None
) -> Generator[Config, None, None]:
    """Initializes all targets

    This function will not run aynthing like `run` but rather, as a context manager,
    enable the user to execute whatever she wants.

    .. code-block:: python

        with init(config=config, targets=my_targets):
            func(config)

        # Is equivalent to
        run(config=config, targets=my_targets, func=func)


    :param config: The config to be used if None a new one is created
    :param targets: the targets to be run
    """
    if config is None:
        assert targets is not None
        config = Config(targets=targets)
    else:
        assert targets is None

    assert isinstance(config, Config)

    if iscoroutinefunction(config.func):
        # pylint: disable=import-outside-toplevel
        from .units import ASYNC_UNIT
        config.add_target(ASYNC_UNIT)

    # Start initializing
    set_config(config)
    wrapper_func = config.init()

    if wrapper_func is not None:
        raise Exception("Can't call wrapper func {} on init".format(wrapper_func))

    try:
        yield config
    finally:
        config.exit()
