import pytest

from ..command import Command
from ..config import Config, config_unit, init, run
from ..units.argparse import (init_arg_parser, init_arg_subparser,
                              parse_parameters)
from ..units.command import run_command
from ..units.config import parse_config
from ..units.logging import set_log_level


class FakeModule:
    def __init__(self):
        self.__ignore_this__ = "__ignore_this__"
        self.loaded_config = True

    def __dir__(self):
        return ["__ignore_this__", "loaded_config"]


def mock_config_load_from_module_path(self, path):
    assert path == "config.py"
    self.load_from_module(FakeModule())

def test_config(mocker):
    mocker.patch("sys.argv", ["file", "-vvv", "-c", "config.py"])
    mocker.patch("command.Config.load_from_module_path", mock_config_load_from_module_path)

    with init(targets=[init_arg_parser]) as config:
        assert "__ignore_this__" not in config
        assert config["loaded_config"] == True
        assert config["ARGS"].verbose == 3
        assert config["ARGS"].config == "config.py"
        assert len(config["ARGS"].blacklist_target) == 0
        assert len(config["ARGS"].disable_target) == 0
        assert len(config["ARGS"].target) == 0
        assert init_arg_parser in config.active_units
        assert config.active_units[init_arg_parser] == None
        assert parse_config in config.active_units
        assert config.active_units[parse_config] == None
        assert len(config.active_units) == 2



def test_help_before_command(mocker, capsys):
    mocker.patch("sys.argv", ["file", "-vvv", "-c", "config.py", "-h"])
    mocker.patch("command.Config.load_from_module_path", mock_config_load_from_module_path)

    with pytest.raises(SystemExit):
        with init(targets=[init_arg_parser, parse_parameters]) as config:
            pass

    assert len(capsys.readouterr().err) > 0


def test_help_after_command(mocker, capsys):
    mocker.patch("sys.argv", ["file", "-vvv", "-c", "config.py", "testcommand", "-h"])
    mocker.patch("command.Config.load_from_module_path", mock_config_load_from_module_path)
    called = False


    class TestCommand(Command):
        name = "testcommand"

        def run(self, config):
            nonlocal called
            called = True


    with pytest.raises(SystemExit):
        run(targets=[run_command])

    assert called == False
    assert len(capsys.readouterr().out) > 0


def test_run_command(mocker, capsys):
    mocker.patch("sys.argv", ["file", "-vvv", "-c", "config.py", "testcommand2"])
    mocker.patch("command.Config.load_from_module_path", mock_config_load_from_module_path)
    called = False


    class TestCommand(Command):
        name = "testcommand2"

        def run(self, config):
            nonlocal called
            called = True

            assert parse_parameters in config.active_units
            assert init_arg_subparser in config.active_units
            assert parse_config in config.active_units
            assert set_log_level in config.active_units


    run(targets=[run_command])

    assert called == True


def test_argparser_for_command(mocker, capsys):
    mocker.patch("sys.argv", ["file", "-vvv", "-c", "config.py", "testcommand2", "--test-this"])
    mocker.patch("command.Config.load_from_module_path", mock_config_load_from_module_path)
    called = False


    class TestCommand(Command):
        name = "testcommand2"

        def run(self, config):
            nonlocal called
            called = True

            assert parse_parameters in config.active_units
            assert init_arg_subparser in config.active_units
            assert parse_config in config.active_units
            assert set_log_level in config.active_units
            assert config["ARGS"].test_this == True

        @classmethod
        def get_arguments(cls, parser):
            parser.add_argument("--test-this", action="store_true", default=False)

    run(targets=[run_command])

    assert called == True


def test_target_command(mocker, capsys):
    mocker.patch("sys.argv", ["file", "-vvv", "-c", "config.py", "testcommand3", "--test-this"])
    mocker.patch("command.Config.load_from_module_path", mock_config_load_from_module_path)
    called = False

    @config_unit
    def testcommand_unit(config):
        pass

    class TestCommand(Command):
        name = "testcommand3"
        targets = [testcommand_unit]

        def run(self, config):
            nonlocal called
            called = True

            assert parse_parameters in config.active_units
            assert init_arg_subparser in config.active_units
            assert parse_config in config.active_units
            assert set_log_level in config.active_units
            assert testcommand_unit in config.active_units
            assert config["ARGS"].test_this == True

        @classmethod
        def get_arguments(cls, parser):
            parser.add_argument("--test-this", action="store_true", default=False)

    run(targets=[run_command])

    assert called == True
