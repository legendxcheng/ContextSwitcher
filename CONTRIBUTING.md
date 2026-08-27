# Contributing to ContextSwitcher

Thank you for helping improve ContextSwitcher. Bug reports, focused feature proposals, documentation improvements, translations, and pull requests are welcome.

## Before opening an issue

- Search existing issues first.
- Include your Windows version and whether you ran a packaged build or the Python source.
- Describe the expected behavior, the actual behavior, and the smallest reliable reproduction.
- Remove private window titles, task names, user names, and local paths from screenshots, logs, and JSON files.
- For a suspected vulnerability, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.

## Development setup

ContextSwitcher is Windows-only. The current development baseline is Python 3.10 or later.

```powershell
git clone https://github.com/legendxcheng/ContextSwitcher.git
cd ContextSwitcher
py -3.10 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
```

Run the application:

```powershell
.\.venv\Scripts\python main.py
```

Run the tests:

```powershell
.\.venv\Scripts\python -m pytest tests -q
```

## Project map

- `main.py`: application startup and component wiring
- `core/`: task, hotkey, window restoration, time tracking, and optional Herdr integration
- `gui/qt/`: PySide6 interface
- `utils/`: configuration, persistence, localization, and supporting utilities
- `locales/`: bundled display-language catalogs
- `tests/`: automated tests
- `installer/`: Inno Setup configuration

## Localization changes

Application-owned user-facing text should use `tr("stable.key")`; do not add new hard-coded interface text.

When adding or changing a translation:

1. Update both `locales/zh-CN.json` and `locales/en-US.json`.
2. Keep the key sets and format placeholders identical.
3. Run `python -m pytest tests/test_localization.py -q`.
4. Check the affected interface in both languages when practical.

User-authored content, external application names, and file paths must not be translated.

## Pull requests

- Keep each pull request focused on one problem.
- Add or update tests for behavior changes.
- Preserve backward compatibility for data in `%APPDATA%\ContextSwitcher` whenever possible.
- Explain any user-visible change and include a screenshot for interface changes.
- Confirm that `python -m pytest tests -q` passes.
- Do not commit generated builds, virtual environments, runtime data, or personal task data.

By contributing, you agree that your contribution will be licensed under the repository's [MIT License](LICENSE).
