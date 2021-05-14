# Ackermann - Command/Config Library

This library simplifies the startup process of a more complicated python project with multiple
subcommands, a complicated configuration, aswell as certain targets that need to be run
or initialized before starting commands in a specific order.

The point of this library is to easily provide a way to setup a commandline interface using
`logging` and `argparse` and `contextvars`  that looks like this:

```bash

my-programm -vvv -c <config_file.py> my-custom-command --my-custom-options

```

While providing a default way of starting the programm you might implemented way. Just have a look
at `ackermann.units`. The main purpose of this library is just to provide an extentable way to
implement commands and startup targets.


## Usage

The most simple setup is just to call `ackermann.run` in your `__main__` file, like so:

```python
from ackermann import run
from ackermann.units import run_command

run(targets=[run_command])
```

Now if you execute your module with `python -m <module>` you can specify a config with `-c`
change the verbosity level with `-v` and specify a subcommand.


## Commands

If you want to write your own command you can do so:

```python
from ackermann import Command, Config
from argparse import ArgumentParser
from time import sleep


class MyCommand(Command):
    name = "my-command"
    @classmethod
    def get_arguments(cls, parser: ArgumentParser):
        parser.add_argument("-s", "--skip", action="store_true")

    def run(self, config: Config):
        if config["ARGS"].skip:
            print("You wanted to skip")
        else:
            print("We are doing it as you are not skipping") 
            sleep(1000)
```

If you run your program as suggested you are able to run this command with:

```bash

python -m <project> my-command -s

```


The same works for `async` commands aswell:


```python
from ackermann import Command, Config
from argparse import ArgumentParser
from asyncio import sleep


class MyAsyncCommand(Command):
    name = "my-async-command"
    is_async = True

    @classmethod
    def get_arguments(cls, parser: ArgumentParser):
        parser.add_argument("-s", "--skip", action="store_true")

    async def async_run(self, config: Config):
        if config["ARGS"].skip:
            print("You wanted to skip")
        else:
            print("We are doing it as you are not skipping") 
            await sleep(1000)
```

running this command would look like this:

```bash

python -m <project> my-async-command -s
```


## Targets / Units

More complicated commands might want to reuse certain parts of code to initialize their project in
the correct way. For this `ackermann` has `ConfigUnit`s. These work pretty similiar to context
managers around your command.

A unit might be defined like this:

```python

from ackermann import Config, config_unit

@config_unit
async def do_sth(config: Config):
    print("I want to do sth before my command starts")
    yield
    print("Now I need to cleanup as the command finished")
```

This unit will not run by default, but it must be explicitly stated in the command. Using the
`targets` variable. Config units might depend on each other, might conflict with one another or must
be run in a certain order.
They might also force the programm to be run in an async context or on multiple processors.


## Signals

If your programm needs to signal certain parts of code about it's state you might also add signals.
To your config by default before executing a command ackermann will signal `ready` and after
exiting a command it will signal `stopping`. This might be used to signal systemd in case of using
a notify service.


## Config Variables

All commands, units and signals are called with the current instance of `Config` which itself
stores configuration variables that might be stored in a python module supplied with the `-c` flag.
If you want to explicitly tell the programm about these variables you can use the small wrapper
`ackermann.ConfigVar` around `contextvars.ContextVar` which allows you to specify the format,
type, and default value for a config variable.

These variables might then be imported in your programm without worrying where the get the correct
value like so:

```python
from ackermann import ConfigVar

config_my_config_var = ConfigVar("MY_CONFIG_VAR", description="Does something", type=int, default=0)

# At some point in the code

def do_sth():
    my_config_var_value = config_my_config_var.get()
```

One benefit of using this interface is that you can easily check the variables set when starting the
programm with the `-V` flag.
