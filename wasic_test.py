"""Minimal library bootstrap example (requires connected hardware)."""
from addons.loader import load_addons
from connections import Connections
from tasks import Tasks

def use_as_library():
    load_addons()
    Connections().fetch_all_instruments()
    Tasks().run_task("Thermal tracking")
