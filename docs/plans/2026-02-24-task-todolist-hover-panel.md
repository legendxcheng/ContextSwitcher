# Task TodoList Hover Panel Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a per-task lightweight TodoList that appears below the main panel when the user hovers over the ContextSwitcher window, and supports creating items and marking items as completed for the current active task.

**Architecture:** Extend `Task` with a persisted `todo_items` field in existing `tasks.json`. Add dedicated `TaskManager` APIs for add/toggle operations and trigger `on_task_updated` callbacks so autosave remains centralized. In Qt UI, add a collapsible todo panel in `QtMainWindow`; show it on hover, bind it to `TaskManager.get_current_task()`, and sync edits through manager APIs.

**Tech Stack:** Python 3.10+, dataclasses, PySide6 widgets/signals, pytest.

---

### Task 1: Add task-level todo model and manager APIs

**Files:**
- Modify: `core/task_manager.py`
- Test: `tests/test_task_manager_todo.py`

**Step 1: Write failing tests for todo default/add/toggle behavior**

```python
def test_add_task_starts_with_empty_todo_items():
    tm = TaskManager()
    task = tm.add_task("T1")
    assert task is not None
    assert task.todo_items == []


def test_add_and_toggle_todo_item():
    tm = TaskManager()
    task = tm.add_task("T1")
    assert tm.add_todo_item(task.id, "Write unit tests") is True
    assert task.todo_items[0]["text"] == "Write unit tests"
    assert task.todo_items[0]["completed"] is False

    assert tm.set_todo_item_completed(task.id, 0, True) is True
    assert task.todo_items[0]["completed"] is True
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_task_manager_todo.py -q`
Expected: FAIL with missing `todo_items` field and missing API methods.

**Step 3: Add minimal task todo field and manager APIs**

```python
@dataclass
class Task:
    ...
    todo_items: List[Dict[str, Any]] = field(default_factory=list)


def add_todo_item(self, task_id: str, text: str) -> bool:
    ...


def set_todo_item_completed(self, task_id: str, item_index: int, completed: bool) -> bool:
    ...
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_task_manager_todo.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add core/task_manager.py tests/test_task_manager_todo.py
git commit -m "feat: add task todo model and task manager todo APIs"
```

### Task 2: Add persistence compatibility for todo_items

**Files:**
- Modify: `core/task_manager.py`
- Modify: `utils/data_storage.py`
- Test: `tests/test_task_manager_todo.py`

**Step 1: Write failing compatibility tests for Task.from_dict normalization**

```python
def test_from_dict_accepts_missing_todo_items():
    task = Task.from_dict({"id": "t1", "name": "Demo", "status": "todo", "bound_windows": []})
    assert task.todo_items == []


def test_from_dict_normalizes_legacy_todo_shapes():
    raw = {
        "id": "t1",
        "name": "Demo",
        "status": "todo",
        "bound_windows": [],
        "todo_items": [
            "Legacy plain text",
            {"text": "Legacy done", "done": True},
            {"text": "Modern", "completed": False}
        ]
    }
    task = Task.from_dict(raw)
    assert [item["text"] for item in task.todo_items] == ["Legacy plain text", "Legacy done", "Modern"]
    assert [item["completed"] for item in task.todo_items] == [False, True, False]
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_task_manager_todo.py -q`
Expected: FAIL on todo normalization assertions.

**Step 3: Implement normalization and version metadata update**

```python
@staticmethod
def _normalize_todo_items(raw_items: Any) -> List[Dict[str, Any]]:
    ...

@classmethod
def from_dict(cls, data: Dict[str, Any]) -> "Task":
    ...
    data["todo_items"] = cls._normalize_todo_items(data.get("todo_items", []))
```

And in storage metadata:

```python
"version": "1.3.0"
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_task_manager_todo.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add core/task_manager.py utils/data_storage.py tests/test_task_manager_todo.py
git commit -m "feat: persist task todo items with backward-compatible loading"
```

### Task 3: Build hover TodoList panel in Qt main window

**Files:**
- Modify: `gui/qt/qt_main_window.py`
- Optional Modify: `gui/qt/styles/dark_theme.qss`
- Test: `tests/test_qt_main_window_todo_panel.py`

**Step 1: Write failing UI smoke tests for hover show/hide behavior**

```python
def test_todo_panel_hidden_by_default(qt_main_window):
    assert qt_main_window.todo_panel.isVisible() is False


def test_hover_shows_and_leave_hides_todo_panel(qt_main_window, qapp):
    qapp.sendEvent(qt_main_window, QEvent(QEvent.Enter))
    assert qt_main_window.todo_panel.isVisible() is True

    qapp.sendEvent(qt_main_window, QEvent(QEvent.Leave))
    assert qt_main_window.todo_panel.isVisible() is False
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_qt_main_window_todo_panel.py -q`
Expected: FAIL because `todo_panel` and hover logic do not exist.

**Step 3: Implement Todo panel structure and hover toggle**

```python
# in _setup_ui
self.todo_panel = self._create_todo_panel()
self.todo_panel.setVisible(False)
layout.addWidget(self.todo_panel)

# override events
def enterEvent(self, event):
    super().enterEvent(event)
    self._set_todo_panel_visible(True)

def leaveEvent(self, event):
    self._set_todo_panel_visible(False)
    super().leaveEvent(event)
```

Panel content (minimal): title label, checklist (`QListWidget` with checkboxes), input (`QLineEdit`), add button (`+`).

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_qt_main_window_todo_panel.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add gui/qt/qt_main_window.py tests/test_qt_main_window_todo_panel.py gui/qt/styles/dark_theme.qss
git commit -m "feat: add hover todo panel below main panel in qt window"
```

### Task 4: Connect panel interactions to current active task and verify end-to-end

**Files:**
- Modify: `gui/qt/qt_main_window.py`
- Test: `tests/test_qt_main_window_todo_panel.py`

**Step 1: Write failing interaction tests for add/complete flow**

```python
def test_add_todo_uses_current_active_task(qt_main_window, fake_task_manager):
    fake_task_manager.set_current_task("t1")
    qt_main_window.todo_input.setText("Ship MVP")
    qt_main_window._on_add_todo_clicked()
    assert fake_task_manager.get_task_by_id("t1").todo_items[0]["text"] == "Ship MVP"


def test_checking_item_marks_completed(qt_main_window, fake_task_manager):
    fake_task_manager.seed_todo("t1", "Write docs", completed=False)
    qt_main_window._refresh_todo_panel()
    item = qt_main_window.todo_list.item(0)
    item.setCheckState(Qt.Checked)
    assert fake_task_manager.get_task_by_id("t1").todo_items[0]["completed"] is True
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_qt_main_window_todo_panel.py -q`
Expected: FAIL on missing handler wiring.

**Step 3: Implement add/complete handlers and panel refresh logic**

```python
def _refresh_todo_panel(self):
    current_task = self.task_manager.get_current_task()
    ...

def _on_add_todo_clicked(self):
    ...

def _on_todo_item_changed(self, item):
    ...
```

Behavior rules:
- Data source is always `task_manager.get_current_task()`.
- Empty text is ignored.
- If no active task, disable input and show guidance text.
- Item completion updates through `TaskManager` APIs only.

**Step 4: Run focused and regression tests**

Run: `python -m pytest tests/test_task_manager_todo.py tests/test_qt_main_window_todo_panel.py -q`
Expected: PASS.

Run: `python -m pytest tests/test_explorer_helper_simple.py -q`
Expected: PASS (sanity regression).

**Step 5: Manual verification in app**

Run: `python main.py --qt`
Checklist:
- Hover main panel => todo panel appears below main panel.
- Move mouse away => todo panel hides.
- Switch active task => panel shows that task's todos.
- Add todo => persists after restart.
- Check/uncheck todo => state persists after restart.

**Step 6: Commit**

```bash
git add gui/qt/qt_main_window.py tests/test_qt_main_window_todo_panel.py tests/test_task_manager_todo.py
git commit -m "feat: support per-task hover todo add and complete flow"
```
