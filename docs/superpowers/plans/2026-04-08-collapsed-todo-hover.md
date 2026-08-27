# Collapsed Main Window Hover Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the floating main window compact by default with a single-line current-task summary, and expand to the full interface only on hover.

**Architecture:** Add a compact summary row to the main window content, hide the full interface while collapsed, and restore the full interface on hover. Preserve existing task and Todo data behaviors, and add focused tests around the new idle/hover contract.

**Tech Stack:** Python, PySide6, unittest

---

## Chunk 1: Spec Lock-In

### Task 1: Record the approved UI behavior

**Files:**
- Create: `docs/superpowers/specs/2026-04-08-collapsed-todo-hover-design.md`

- [ ] **Step 1: Write the approved behavior summary**
- [ ] **Step 2: Save the design note in the specs directory**

## Chunk 2: TDD for Popup States

### Task 2: Add a failing test for collapsed idle behavior

**Files:**
- Modify: `tests/test_qt_main_window_todo_panel.py`
- Test: `tests/test_qt_main_window_todo_panel.py`

- [ ] **Step 1: Write the failing test**

```python
def test_window_is_collapsed_to_current_task_by_default(self):
    self.assertEqual("Task 1", self.window.compact_task_label.text())
    self.assertFalse(self.window.task_table.isVisible())
    self.assertFalse(self.window.todo_popup.isVisible())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_qt_main_window_todo_panel.py -k collapsed -v`
Expected: FAIL because the compact summary widgets do not exist yet

### Task 3: Implement the minimal collapsed/expanded UI

**Files:**
- Modify: `gui/qt/qt_main_window.py`
- Test: `tests/test_qt_main_window_todo_panel.py`

- [ ] **Step 1: Add a compact summary row to the main window**
- [ ] **Step 2: Add main-window state helpers for collapsed vs expanded**
- [ ] **Step 3: Change hover handling to expand on enter and collapse on leave**
- [ ] **Step 4: Keep window width stable while collapsed/expanded**

- [ ] **Step 5: Run the focused test to verify it passes**

Run: `python -m pytest tests/test_qt_main_window_todo_panel.py -k collapsed -v`
Expected: PASS

### Task 4: Re-run the existing Todo and hover coverage

**Files:**
- Test: `tests/test_qt_main_window_todo_panel.py`

- [ ] **Step 1: Update existing visibility assertions to match collapsed-by-default behavior**
- [ ] **Step 2: Run the Todo popup test file**

Run: `python -m pytest tests/test_qt_main_window_todo_panel.py -v`
Expected: PASS

### Task 5: Narrow the expanded window width to 360px

**Files:**
- Modify: `gui/qt/widgets/frameless_window.py`
- Modify: `tests/test_qt_main_window_todo_panel.py`
- Test: `tests/test_qt_main_window_todo_panel.py`

- [ ] **Step 1: Write the failing test**

```python
def test_expanded_window_targets_360px_width(self):
    self.window._expand_main_window()
    self._app.processEvents()
    self.assertEqual(360, self.window.width())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_qt_main_window_todo_panel.py -k expanded_window_targets_360px_width -v`
Expected: FAIL because the current expanded width is 420px

- [ ] **Step 3: Write minimal implementation**
- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_qt_main_window_todo_panel.py -k expanded_window_targets_360px_width -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-04-08-collapsed-todo-hover-design.md docs/superpowers/plans/2026-04-08-collapsed-todo-hover.md tests/test_qt_main_window_todo_panel.py gui/qt/qt_main_window.py
git commit -m "feat: collapse todo popup until hover"
```
