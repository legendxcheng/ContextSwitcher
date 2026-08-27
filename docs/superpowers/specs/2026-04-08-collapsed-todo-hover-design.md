# Collapsed Main Window Hover Design

## Goal

Reduce the footprint of the floating tool itself when it is idle. The non-hover state should keep only a single summary row for the current active task. Hovering the window should expand the full main interface.

## Context

The PySide6 main window currently stays fully expanded, which takes too much screen space while idle.

## Decision

Use the main floating window itself with two visual states:

1. Collapsed state
   - Always visible while the main window is visible
   - Shows one compact summary row only
   - Summary text is the current active task name
   - If there is no active task, show a fallback message

2. Expanded state
   - Triggered by hovering the main window
   - Shows the existing full task manager interface
   - Width stays stable; the main change is vertical footprint

## Interaction Notes

- Leaving the main window should collapse back to the summary row instead of staying expanded.
- The main window itself should shrink in height while collapsed.
- The summary row should be compact enough to consume roughly one line of vertical space.

## Width Adjustment

- The expanded main window should target a width of `360px` instead of `420px`.
- This change is intended to restore the tighter visual footprint of the original tool.
- Hover/collapse behavior stays unchanged for this adjustment.

## Files

- Modify `gui/qt/qt_main_window.py`
- Modify `tests/test_qt_main_window_todo_panel.py`
