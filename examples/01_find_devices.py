"""List every instrument on the bench and which role it fills.

    python examples/01_find_devices.py [--sim]
"""
from _common import maybe_sim

from vescentcomb import discovery
from vescentcomb.settings import Settings

maybe_sim()
settings = Settings()                       # same file the GUI uses
res = discovery.assign_roles(discovery.scan_all(progress=print), settings.get("roles", {}))
print(f"\nscan took {res.duration_s:.1f} s")
for f in res.found:
    print(f"  {f.role or '-':7s} {f.kind:14s} {f.serial:20s} {f.address:45s} {f.status}")
for role, saved in res.missing.items():
    print(f"  MISSING {role}: {saved}")
