"""Basic start script to start a command

The default target is always run_command
"""
from .config import run
from .units import run_command

run(targets=[run_command])
