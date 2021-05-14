"""Ackermann exceptions"""


class CycleException(Exception):
    """There is a circular dependency

    Thus this setup cannot be run
    """


class StopInitException(Exception):
    """Stops the init process all together
    """
