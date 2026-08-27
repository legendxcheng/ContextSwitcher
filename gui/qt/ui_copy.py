"""Compatibility accessors for shared user-facing Qt copy."""

from utils.localization import tr


def double_alt_summon_copy() -> str:
    return tr("welcome.summon_desc")


__all__ = ["double_alt_summon_copy"]
