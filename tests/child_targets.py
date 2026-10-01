"""Tiny trial targets used by test_child to exercise the process supervisor."""
import time

from harness.shared import ledger


def finish(**_):
    return {"stop": "final_answer"}


def hold(**_):
    return {"hold": True, "paused": True}


def runaway(**_):
    while True:
        ledger.record("tool")
        time.sleep(0.05)


def boom(**_):
    raise ValueError("kaboom")
