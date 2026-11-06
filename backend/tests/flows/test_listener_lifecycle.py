"""Idle polling must not delay Stop or hide a still-running check."""

import threading

import pytest

from backend.flows.listener_base import BaseEventListener


class ControlledListener(BaseEventListener):
    def __init__(self, *, block=False, poll_interval=60):
        super().__init__(project_id=1, poll_interval=poll_interval)
        self.entered = threading.Event()
        self.release = threading.Event()
        if not block:
            self.release.set()

    def check(self):
        self.entered.set()
        self.release.wait(timeout=2)


def attach_existing_worker(listener):
    """Simulate a registered poller from the prior version; public start may no longer create one."""
    listener._thread = threading.Thread(target=listener._poll_loop, daemon=True)
    listener._thread.start()


def test_stop_wakes_an_idle_listener_without_waiting_for_its_poll_interval():
    listener = ControlledListener()
    attach_existing_worker(listener)
    assert listener.entered.wait(timeout=1)
    stopped = threading.Event()

    def stop():
        listener.stop()
        stopped.set()

    stopper = threading.Thread(target=stop, daemon=True)
    stopper.start()
    assert stopped.wait(timeout=0.5), "Stop remained blocked on the polling interval"
    assert not listener.is_running
    stopper.join(timeout=1)


def test_stop_timeout_keeps_the_live_listener_owned_and_prevents_restart():
    listener = ControlledListener(block=True, poll_interval=0.01)
    attach_existing_worker(listener)
    assert listener.entered.wait(timeout=1)
    try:
        with pytest.raises(TimeoutError, match="still running"):
            listener.stop(timeout=0)
        assert listener.is_running
        with pytest.raises(RuntimeError, match="stopping"):
            listener.start()
    finally:
        listener.release.set()
        listener.stop()
    assert not listener.is_running
