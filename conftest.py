"""Shared fixtures. Every test runs against the simulated bench (no hardware needed).

``bench`` loads every built-in add-on, installs the simulator and connects all roles.
"""
import pytest

from vescentcomb import addonkit, discovery, sim
from vescentcomb.settings import Settings


@pytest.fixture(scope="session")
def all_addons(tmp_path_factory):
    addonkit.reset()
    s = Settings(tmp_path_factory.mktemp("addons") / "settings.json", autosave=False)
    s.set("addons.dirs", [])                       # built-in add-ons only
    infos = addonkit.load_enabled(s, include_all=True, auto_install=False)
    bad = {k: v.error for k, v in infos.items() if v.state != "loaded"}
    assert not bad, bad
    return s


@pytest.fixture
def world(all_addons):
    w = sim.install(speed=60)
    yield w
    sim.uninstall()


@pytest.fixture
def settings(tmp_path):
    s = Settings(tmp_path / "settings.json", autosave_delay=0.05)
    s.set("addons.dirs", [])
    return s


@pytest.fixture
def bench(world, settings):
    b = discovery.connect_all(settings)
    yield b
    b.close()
