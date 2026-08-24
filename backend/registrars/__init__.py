"""
Registrar registry.

Register every adapter here. The rest of the app (API + UI) is driven by
this dict, so adding a registrar is: create an adapter file, import it, add
one line below.
"""
from .kfintech import KFintechAdapter
from .mufg import MufgAdapter

# key -> adapter instance
REGISTRARS = {
    KFintechAdapter.key: KFintechAdapter(),
    MufgAdapter.key: MufgAdapter(),
    # Future: add new adapters here, e.g.
    # BigshareAdapter.key: BigshareAdapter(),
}


def list_registrars() -> list[dict]:
    """Metadata for the UI's registrar switcher, in insertion order."""
    return [a.meta() for a in REGISTRARS.values()]


def get(key: str):
    return REGISTRARS.get(key)
