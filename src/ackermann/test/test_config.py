import logging
from asyncio import sleep

import pytest

from ..config import Config, ConfigUnit, _param_to_list, config_unit, run
from ..units import ASYNC_UNIT


@pytest.fixture(scope="function")
def clean_config_units():
    old = ConfigUnit.units
    ConfigUnit.units = old.copy()
    yield None
    ConfigUnit.units = old


def test_param_to_list():
    l = []
    assert id(_param_to_list(l)) != id(l)
    assert _param_to_list(None) == []
    assert _param_to_list([1]) == [1]
    assert _param_to_list(True) == [True]


def test_config_decorator(clean_config_units):
    @config_unit(description="description")
    def step(config):
        return config


    # TODO path name is kinda moot
    unit = ConfigUnit.units["command.test.test_config.step"]

    assert unit == step
    assert step.description == "description"
    assert step.name == "step"
    assert step.contains == []
    assert step.belongs == []
    assert step.depends == []
    assert step.before == []
    assert step.after == []
    assert step.conflicts == []
    assert step("test") == "test"


    @config_unit(belongs=step)
    def step2(config):
        return config

    unit2 = ConfigUnit.units["command.test.test_config.step2"]
    assert unit2 == step2

    assert step2.belongs == [step]
    assert step2.name == "step2"
    assert step2.contains == []
    assert step2.depends == []
    assert step2.before == []
    assert step2.after == []
    assert step2.conflicts == []
    assert step2("test") == "test"


def test_run1(clean_config_units, caplog):
    caplog.set_level(logging.DEBUG, logger="command.config")

    @config_unit
    def base(config):
        config["base"] = "base"
        yield
        del config["base"]

    @config_unit(belongs=base)
    def belongs_to_base(config):
        config["belongs"] = "belongs"
        yield
        del config["belongs"]

    @config_unit(before=base, belongs=base)
    def before_base(config):
        assert "base" not in config
        config["before"] = "before"
        yield
        assert "base" not in config
        del config["before"]

    @config_unit(after=base)
    def after_base(config):
        assert "base" in config
        config["after"] = "after"
        yield
        assert "base" in config
        del config["after"]

    @config_unit(depends=[base, after_base], after=[after_base, base])
    def hook_this(config):
        assert "base" in config
        assert "after" in config
        assert "before" in config
        yield
        assert "base" in config
        assert "after" in config
        assert "before" in config

    #assert set(runner.units) == set([before_base, after_base, hook_this, belongs_to_base, base])

    config = Config(targets=[hook_this])
    config.init()

    assert "base" in config
    assert "belongs" in config
    assert "after" in config
    assert "before" in config

    config.exit()
    assert len(config) == 0


def test_async_config_runner(clean_config_units, caplog):
    caplog.set_level(logging.DEBUG, logger="command.config")

    @config_unit
    async def wait_100ms(config):
        config["wait_100ms"] = "wait_100ms"
        await sleep(0.1)
        yield
        del config["wait_100ms"]
        await sleep(0.1)

    @config_unit
    def pre_or_post_async(config):
        config["pre_async"] = "pre_async"
        yield
        del config["pre_async"]

    @config_unit(after=wait_100ms)
    async def wait_50ms(config):
        config["wait_50ms"] = "wait_50ms"
        await sleep(0.05)
        yield
        del config["wait_50ms"]
        await sleep(0.05)

    async def func(config):
        await sleep(0.1)

        assert config["wait_100ms"] == "wait_100ms"
        assert config["wait_50ms"] == "wait_50ms"
        assert config["pre_async"] == "pre_async"

    config = Config(func=func, targets=[wait_100ms, pre_or_post_async, wait_50ms])
    run(config=config)

    assert config.variables == {}


def test_one_target_tomuch(clean_config_units, caplog):
    caplog.set_level(logging.DEBUG, logger="command.config")

    @config_unit
    def first(config):
        pytest.fail("Should not run")
        yield

    @config_unit
    def second(config):
        config["second"] = "second"
        yield
        del config["second"]

    def func(config):
        assert "second" in config

    config = Config(func=func, targets=[second])
    run(config=config)

    assert config.variables == {}


def test_add_target(clean_config_units, caplog):
    caplog.set_level(logging.DEBUG, logger="command.config")

    @config_unit
    def first(config):
        config["first"] = "first"
        yield
        del config["first"]

    @config_unit(after=first)
    def third(config):
        assert "first" in config
        config["third"] = "third"
        yield
        del config["third"]

    @config_unit(before=third)
    def second(config):
        config["second"] = "second"
        config.add_target(first)
        yield
        del config["second"]

    def func(config):
        if "first" not in config:
            pytest.fail("first did not run")
        if "second" not in config:
            pytest.fail("second did not run")
        if "third" not in config:
            pytest.fail("third did not run")

    config = Config(func=func, targets=[second, third])
    run(config=config)

    assert config.variables == {}


def test_discover_target(clean_config_units, caplog):
    caplog.set_level(logging.DEBUG, logger="command.config")

    @config_unit
    def target(config):
        pass

    @config_unit(belongs=target)
    def second(config):
        config["second"] = "second"
        @config_unit(belongs=target)
        def first(config):
            config["first"] = "first"
            yield
            del config["first"]

        yield
        del config["second"]

    def func(config):
        if "first" not in config:
            pytest.fail("first did not run")
        if "second" not in config:
            pytest.fail("second did not run")

    config = Config(func=func, targets=[target])
    run(config=config)

    assert config.variables == {}


def test_blacklist(clean_config_units, caplog):
    caplog.set_level(logging.DEBUG, logger="command.config")


def test_add_blacklist(clean_config_units, caplog):
    caplog.set_level(logging.DEBUG, logger="command.config")


def test_belongs_unit_as_one(clean_config_units, caplog):
    caplog.set_level(logging.DEBUG, logger="command.config")
    # I don't even know how to test this reliably
