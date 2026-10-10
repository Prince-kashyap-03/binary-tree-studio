# Binary Tree Studio

**A visual, interactive binary tree explorer built with Python (Tkinter) + a C engine.**

Binary Tree Studio lets you build, edit, and animate binary trees entirely through a graphical interface — no command line needed after setup. You can insert node values and instantly see all four traversals, or give the app a pair of traversal sequences and watch it reconstruct the original tree. A full-featured tree editor lets you click to select nodes, add children on either side, edit values, delete subtrees, undo/redo changes, save and load trees as JSON, and generate random trees on demand. A live sidebar classifies the current tree into every standard tree type in real time.

---

## Features

### Three Tabs, One Shared Tree

All three tabs operate on the **same** underlying tree owned by the C engine, so you can build a BST in Tab 1 and immediately edit it by hand in Tab 3.

| Tab | Name | What it does |
|-----|------|--------------|
| 1 | **Nodes → Traversals** | Type values (or click *Generate* for random ones), click *Build tree* to insert them into a BST, and see all four traversals instantly. |
| 2 | **Traversals → Tree** | Paste one or two traversal sequences and click *Reconstruct tree* to rebuild the unique tree they describe (see the table below). |
| 3 | **Tree Editor** | Full interactive editor: click nodes to select, use dashed `+` slots to add a child on a specific side, right-click for a context menu, Ctrl+Z / Ctrl+Y to undo/redo, Save/Load JSON, random tree generator. |

### Interactive Editing (Tab 3)

- **Click** a node to select it (highlighted in gold).
- **Dashed `+` circles** appear on the available child slots of the selected node. Click one to immediately add a child there.
- **Right-click** a node for: *Add Left Child*, *Add Right Child*, *Edit value*, *Delete subtree*.
- **Ctrl+Z** / **Ctrl+Y** (or *Ctrl+Shift+Z*) to undo and redo up to 100 steps.
- **Save JSON** / **Load JSON** to persist trees to disk and reload them later. (Saved `.json` files are in `.gitignore` by default; copy them into `examples/` if you want to commit them.)
- **Random tree** with a configurable node count (1–127).

### Four Traversals with Animation

The output panel (visible in all tabs) shows the current tree's:
- **Preorder** (Root, Left, Right)
- **Inorder** (Left, Root, Right)
- **Postorder** (Left, Right, Root)
- **Level-order** (breadth-first, level by level)

Press **▶ Animate** next to any traversal to watch the nodes light up in visit order.

### Live Tree-Type Detection

The sidebar on the right classifies the current tree into every standard type in real time, showing ✔ (green) for types that apply and ✘ (grey) for those that don't, each with a brief explanation.

---

## Tree Types Detected

| Type | Definition |
|------|-----------|
| **Full** | Every node has 0 or 2 children — no node has exactly one child. |
| **Perfect** | Full, and every leaf is at the same depth. |
| **Complete** | All levels are full except possibly the last, which is filled left to right. |
| **Height-balanced** | The heights of the left and right subtrees at every node differ by at most 1 (AVL property). |
| **Degenerate (skewed)** | Every node has at most one child, forming a single chain. Subtypes: left-skewed, right-skewed, or zig-zag. |
| **Binary Search Tree** | Inorder traversal is strictly increasing (left subtree < root < right subtree, no duplicates). |
| **Min-Heap** | The tree is complete and every parent value ≤ both its children. |
| **Max-Heap** | The tree is complete and every parent value ≥ both its children. |

---

## Traversal Combinations That Can Rebuild a Tree

| Combination | Rebuilds any binary tree? | Notes |
|-------------|--------------------------|-------|
| **Preorder only** | BST only | For a BST, inserting the preorder sequence in order recreates the exact same tree. |
| **Postorder only** | BST only | Inserting in reverse postorder recreates the BST. |
| **Inorder + Preorder** | ✔ Yes (distinct values) | The preorder root splits the inorder into left/right recursively. |
| **Inorder + Postorder** | ✔ Yes (distinct values) | The postorder root splits the inorder into left/right recursively. |
| **Inorder + Level-order** | ✔ Yes (distinct values) | The first level-order value is the root; subsequent values are partitioned by the inorder split. |
| **Inorder alone** | ✗ No | A BST's inorder is always the sorted sequence, so every BST with the same values produces the *same* inorder — making reconstruction impossible without additional information. Many different tree shapes share the same inorder. |

> **Why inorder alone fails:** Consider values {1, 2, 3}. Their BST inorder is always `1 2 3`, regardless of insertion order. The tree could be a balanced BST (2 at root), a right-skewed chain (1→2→3), or a left-skewed chain (3→2→1). All give inorder `1 2 3`. You need a second sequence to disambiguate.

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│  bst_gui.py  (Python / Tkinter)                  │
│  ─────────────────────────────────────────────── │
│  • Three notebook tabs (build, reconstruct, edit) │
│  • Canvas drawing (nodes, edges, + slots)         │
│  • Animation loop (500 ms per step)               │
│  • Undo/redo stack of cloned tree pointers        │
│  • Save/load JSON via tree_flatten / from_arrays  │
│                                                   │
│  Calls ──────────────────────────────────────►   │
│                                                   │
│  bst_engine.dll / .so / .dylib  (C / ctypes)     │
│  ─────────────────────────────────────────────── │
│  • All tree logic: BST insert, traversals,        │
│    reconstruction, editing, classification,       │
│    statistics, random trees, JSON arrays          │
│  • Python only draws; C owns the memory           │
└──────────────────────────────────────────────────┘
```

### Key design details

- **Auto-compile:** On startup `bst_gui.py` checks whether `bst_engine.dll` (or `.so`/`.dylib`) is absent or older than `bst_engine.c`. If so, it runs `gcc -shared -O2 -static-libgcc -o bst_engine.dll bst_engine.c` automatically. You never need to compile manually.
- **Node addressing:** After every structural change, the GUI calls `tree_flatten()` which assigns contiguous **preorder indices** (root = 0) to all nodes. All editor operations (`add_child`, `set_value`, `delete_subtree`) address nodes by this index, which is refreshed after each call.
- **Memory ownership:** The C engine allocates all `Node` structs. Python holds opaque pointers. The undo stack stores `tree_clone()` snapshots; `tree_free()` is called when they are discarded.

---

## Requirements

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Python | 3.9+ | Must include `tkinter` (standard on Windows) |
| gcc | Any recent | Must be **64-bit** if Python is 64-bit — see Troubleshooting |
| OS | Windows 10+, Linux, macOS | See per-OS notes below |

---

## Installation & Running

### Windows (PowerShell) — Recommended

```powershell
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/binary-tree-studio.git
cd binary-tree-studio

# 2. Create and activate a virtual environment
python -m venv .venv

# If script execution is blocked, run this first (current session only):
Set-ExecutionPolicy -Scope Process RemoteSigned

.\.venv\Scripts\Activate.ps1

# 3. Install dependencies (none — just confirms requirements.txt is satisfied)
pip install -r requirements.txt

# 4. Run
python bst_gui.py
```

The C engine is compiled automatically on the first launch. A window opens with a sample BST already drawn.

### Linux

```bash
# Install tkinter if missing (Debian/Ubuntu):
sudo apt install python3-tk

# Install gcc if missing:
sudo apt install gcc

git clone https://github.com/YOUR_USERNAME/binary-tree-studio.git
cd binary-tree-studio
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 bst_gui.py
```

### macOS

```bash
# Install Command Line Tools (includes gcc/clang):
xcode-select --install

git clone https://github.com/YOUR_USERNAME/binary-tree-studio.git
cd binary-tree-studio
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 bst_gui.py
```

---

## Usage Guide

### Tab 1 — Nodes → Traversals

1. Type integer values in the **Node values** box (comma- or space-separated).
2. Press **Enter** or click **Build tree** to insert them into a BST. Duplicates are ignored with a note.
3. Or set a count and click **Generate** to insert random values.
4. All four traversals appear in the output panel. Click **▶ Animate** to watch the visit order.

### Tab 2 — Traversals → Tree

1. Choose a **reconstruction mode** from the dropdown.
2. Fill in only the enabled boxes (greyed-out boxes are not needed for the chosen mode).
3. Click **Reconstruct tree**. The app verifies the result and reports an error if the sequences are inconsistent.

### Tab 3 — Tree Editor

| Action | How |
|--------|-----|
| Select a node | Left-click it (turns gold) |
| Add a child | Select a node, then click the dashed `+` on the desired side, *or* use the toolbar buttons |
| Edit a node's value | Select it, click **Edit value** (or right-click → Edit value) |
| Delete a subtree | Select the subtree root, click **Delete subtree** |
| Undo / Redo | **Ctrl+Z** / **Ctrl+Y** (up to 100 steps) |
| Create a new tree from scratch | **Clear tree**, then **Create root** |
| Save / Load | **Save JSON** / **Load JSON** |
| Random tree | Set node count, click **Random tree** |

### Mouse controls

| Input | Effect |
|-------|--------|
| Left-click node | Select |
| Left-click `+` slot | Add child there (prompts for value) |
| Left-click canvas (empty) | Deselect |
| Right-click node | Context menu (Add left/right, Edit, Delete) |
| Middle-click node (macOS) | Same as right-click |

---

## Running the Tests

```powershell
# From the project root (activate venv first)
python test_engine.py
```

**Expected output:**

```
All 1445 checks passed.
```

The test suite exercises the C engine directly via ctypes (no GUI). It covers:

- BST build and insertion order
- All four traversals (preorder, inorder, postorder, level-order)
- All five reconstruction modes (preorder-only BST, postorder-only BST, inorder+preorder, inorder+postorder, inorder+level-order)
- Tree editing (add child, set value, delete subtree, clone)
- Statistics (node count, height, leaves, min/max)
- Tree classification (all 8 types)
- Random tree generation and JSON round-trip (save/load arrays)

---

## Project Structure

```
binary-tree-studio/
│
├── bst_gui.py          # Python Tkinter GUI — all drawing and UI logic
├── bst_engine.c        # C engine — all tree algorithms (compiled on first run)
├── bst_engine.dll      # Compiled engine (Windows); auto-generated, not committed
│
├── test_engine.py      # Self-contained test suite (1445 checks, no pytest needed)
│
├── requirements.txt    # pip freeze output — empty (standard library only)
├── .gitignore          # Excludes .venv/, *.dll, *.pyc, *.json, IDE folders, etc.
├── LICENSE             # MIT License
├── README.md           # This file
│
└── examples/           # (Optional) committed example tree JSON files
    └── .gitkeep
```

---

## Limitations

- **Maximum 127 nodes** per tree (hard limit in the engine, enforced in the GUI).
- **Distinct values required for reconstruction** (Tab 2): the reconstruction algorithms require that all node values are unique. The app validates this and shows an error if duplicates are detected.
- **Duplicates ignored in Tab 1**: when building a BST, duplicate values are silently dropped (the BST property requires strict ordering), and the GUI notes how many were removed.
- **Integer values only**: node values must be whole numbers in the range −10⁹ to 10⁹.

---

## Screenshots

> Place screenshot images in the `assets/` folder and link them here.

```
assets/
├── screenshot_tab1.png    # Nodes → Traversals
├── screenshot_tab2.png    # Traversals → Tree
└── screenshot_tab3.png    # Tree Editor with type panel
```

<!-- TODO: add screenshot — e.g. ![Tab 1 — Nodes to Traversals](assets/screenshot_tab1.png) -->

---

## Troubleshooting

### `OSError: [WinError 193] %1 is not a valid Win32 application`

The DLL bitness doesn't match Python's bitness. This usually means you have a **32-bit MinGW** gcc but **64-bit Python** (or vice versa).

**Check:**
```powershell
python -c "import struct; print(struct.calcsize('P')*8, 'bit Python')"
gcc -dumpmachine
```

If Python is `64 bit` and gcc prints something like `i686-w64-mingw32` (32-bit), you need 64-bit gcc.

**Fix:** Install WinLibs MinGW-w64 (64-bit):
1. Download from <https://github.com/brechtsanders/winlibs_mingw/releases> — pick a `x86_64` (not `i686`) release.
2. Extract it (e.g. to `C:\mingw64`).
3. Add `C:\mingw64\bin` to the **front** of your PATH (System → Advanced → Environment Variables, or `$env:PATH = "C:\mingw64\bin;$env:PATH"` for the current session).
4. Verify: `gcc -dumpmachine` should now print `x86_64-w64-mingw32`.
5. Delete `bst_engine.dll` and restart the app (it will recompile).

### `gcc was not found` / `FileNotFoundError`

gcc is not on your PATH. Solutions:

- **Windows:** Install WinLibs MinGW-w64 as above and add its `bin` folder to PATH.
- **Linux:** `sudo apt install gcc` (Debian/Ubuntu) or `sudo dnf install gcc` (Fedora).
- **macOS:** `xcode-select --install` (installs Apple's clang as `gcc`) or `brew install gcc`.

### Editor / IDE shows stale PATH after installing gcc

Many GUI editors (VS Code, PyCharm, etc.) cache the PATH from the session in which they were launched. If you installed gcc but the app still can't find it:

1. **Close the editor completely** (check the system tray too).
2. Open a fresh PowerShell, verify `gcc --version` works there.
3. Reopen the editor from that shell, or launch the app from the shell directly.

### `ModuleNotFoundError: No module named '_tkinter'` (Linux)

Python was built without tkinter. Install it separately:

```bash
# Debian/Ubuntu
sudo apt install python3-tk

# Fedora / RHEL
sudo dnf install python3-tkinter

# Arch Linux
sudo pacman -S tk
```

Then recreate the virtual environment (tkinter is a system package, not a pip package).

### App window appears but the tree canvas is blank

Resize the window or switch tabs back and forth. If the canvas is consistently blank after the first draw, it may be a DPI scaling issue on high-DPI displays. Try running:

```powershell
python bst_gui.py
```

from a terminal rather than double-clicking the file.

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
