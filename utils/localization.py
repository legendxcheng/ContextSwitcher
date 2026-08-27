"""Key-based localization with resource discovery and locale fallback."""

from __future__ import annotations

import json
import locale as system_locale_module
import sys
import threading
import weakref
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Mapping, Optional, Tuple


SYSTEM_LANGUAGE = "system"
DEFAULT_LANGUAGE = "zh-CN"


@dataclass(frozen=True)
class Language:
    """Metadata for one bundled display language."""

    code: str
    native_name: str
    direction: str = "ltr"
    aliases: Tuple[str, ...] = ()


def normalize_language_code(value: Optional[str]) -> str:
    """Return a consistently cased BCP 47-style language tag."""
    raw = str(value or "").strip().replace("_", "-")
    if not raw:
        return ""

    parts = raw.split("-")
    normalized = [parts[0].lower()]
    for part in parts[1:]:
        if len(part) == 4 and part.isalpha():
            normalized.append(part.title())
        elif len(part) in (2, 3) and part.isalpha():
            normalized.append(part.upper())
        else:
            normalized.append(part)
    return "-".join(normalized)


def _resource_directory() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "locales"
    return Path(__file__).resolve().parent.parent / "locales"


def _flatten_strings(values: Mapping[str, object], prefix: str = "") -> Dict[str, str]:
    flattened: Dict[str, str] = {}
    for name, value in values.items():
        if name == "_meta":
            continue
        key = f"{prefix}.{name}" if prefix else name
        if isinstance(value, Mapping):
            flattened.update(_flatten_strings(value, key))
        elif isinstance(value, str):
            flattened[key] = value
        else:
            raise ValueError(f"Translation value must be a string: {key}")
    return flattened


class Localizer:
    """Load locale resources and hide resolution, fallback, and formatting."""

    def __init__(self, resource_dir: Optional[Path] = None):
        self._resource_dir = Path(resource_dir) if resource_dir else _resource_directory()
        self._languages: Dict[str, Language] = {}
        self._translations: Dict[str, Dict[str, str]] = {}
        self._aliases: Dict[str, str] = {}
        self._listeners: list[weakref.ReferenceType] = []
        self._lock = threading.RLock()
        self._preference = DEFAULT_LANGUAGE
        self._language = DEFAULT_LANGUAGE
        self._load_resources()

    @property
    def preference(self) -> str:
        return self._preference

    @property
    def language(self) -> str:
        return self._language

    @property
    def text_direction(self) -> str:
        return self._languages[self._language].direction

    def available_languages(self) -> Tuple[Language, ...]:
        return tuple(self._languages[code] for code in sorted(self._languages))

    def set_language(
        self,
        preference: Optional[str],
        system_language: Optional[str] = None,
    ) -> str:
        """Resolve a preference, activate it, and notify live UI listeners."""
        normalized_preference = (
            SYSTEM_LANGUAGE
            if str(preference or "").strip().lower() == SYSTEM_LANGUAGE
            else normalize_language_code(preference)
        )
        if not normalized_preference:
            normalized_preference = SYSTEM_LANGUAGE

        candidate = (
            self._detect_system_language()
            if normalized_preference == SYSTEM_LANGUAGE
            else normalized_preference
        )
        if system_language is not None and normalized_preference == SYSTEM_LANGUAGE:
            candidate = system_language

        resolved = self._resolve_language(candidate)
        with self._lock:
            language_changed = resolved != self._language
            self._preference = normalized_preference
            self._language = resolved

        if language_changed:
            self._notify_listeners()
        return resolved

    def translate(self, key: str, **params: object) -> str:
        """Translate one stable key, falling back to Simplified Chinese."""
        with self._lock:
            current = self._translations.get(self._language, {})
            fallback = self._translations[DEFAULT_LANGUAGE]
            template = current.get(key, fallback.get(key, key))
            fallback_template = fallback.get(key, key)

        try:
            return template.format(**params)
        except (KeyError, IndexError, ValueError):
            try:
                return fallback_template.format(**params)
            except (KeyError, IndexError, ValueError):
                return template

    def subscribe(self, callback: Callable[[str], None]) -> None:
        """Register a weak listener for display-language changes."""
        if getattr(callback, "__self__", None) is not None:
            reference = weakref.WeakMethod(callback)
        else:
            reference = weakref.ref(callback)
        with self._lock:
            self._listeners.append(reference)

    def _load_resources(self) -> None:
        if not self._resource_dir.is_dir():
            raise RuntimeError(f"Translation resource directory not found: {self._resource_dir}")

        for path in sorted(self._resource_dir.glob("*.json")):
            with path.open("r", encoding="utf-8") as stream:
                payload = json.load(stream)
            metadata = payload.get("_meta", {})
            code = normalize_language_code(metadata.get("code") or path.stem)
            if not code:
                raise ValueError(f"Translation resource has no locale code: {path}")
            native_name = str(metadata.get("native_name") or code)
            direction = str(metadata.get("direction") or "ltr").lower()
            if direction not in {"ltr", "rtl"}:
                raise ValueError(f"Invalid text direction for {code}: {direction}")
            aliases = tuple(
                normalize_language_code(alias)
                for alias in metadata.get("aliases", [])
                if normalize_language_code(alias)
            )
            self._languages[code] = Language(code, native_name, direction, aliases)
            self._translations[code] = _flatten_strings(payload)

        if DEFAULT_LANGUAGE not in self._translations:
            raise RuntimeError(f"Required fallback language is missing: {DEFAULT_LANGUAGE}")

        for code, language in self._languages.items():
            self._aliases[normalize_language_code(code).casefold()] = code
            for alias in language.aliases:
                self._aliases[alias.casefold()] = code

    def _resolve_language(self, candidate: Optional[str]) -> str:
        normalized = normalize_language_code(candidate)
        exact = self._aliases.get(normalized.casefold())
        if exact:
            return exact

        base = normalized.split("-", 1)[0].casefold()
        matches = [
            code
            for code in self._languages
            if code.split("-", 1)[0].casefold() == base
        ]
        if len(matches) == 1:
            return matches[0]
        return DEFAULT_LANGUAGE

    @staticmethod
    def _detect_system_language() -> str:
        detected = system_locale_module.getlocale()[0]
        return detected or DEFAULT_LANGUAGE

    def _notify_listeners(self) -> None:
        listeners: list[tuple[weakref.ReferenceType, Callable[[str], None]]] = []
        with self._lock:
            for reference in self._listeners:
                callback = reference()
                if callback is not None:
                    listeners.append((reference, callback))

        live_references: list[weakref.ReferenceType] = []
        for reference, callback in listeners:
            try:
                callback(self._language)
            except RuntimeError:
                # PySide wrappers can outlive their deleted C++ objects.
                continue
            live_references.append(reference)

        with self._lock:
            self._listeners = live_references


_localizer: Optional[Localizer] = None


def get_localizer() -> Localizer:
    global _localizer
    if _localizer is None:
        _localizer = Localizer()
    return _localizer


def tr(key: str, **params: object) -> str:
    return get_localizer().translate(key, **params)


__all__ = [
    "DEFAULT_LANGUAGE",
    "SYSTEM_LANGUAGE",
    "Language",
    "Localizer",
    "get_localizer",
    "normalize_language_code",
    "tr",
]
