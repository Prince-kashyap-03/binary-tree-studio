"""
bst_gui.py - Binary Tree Studio (Python GUI + C engine)

Tabs:
  1. Nodes -> Traversals   build a BST from values, see the 4 traversals
  2. Traversals -> Tree    rebuild a tree from traversal sequences
  3. Tree Editor           click nodes, add children on either side, edit,
                           delete, undo/redo, save/load, live tree-type detection

All three tabs share ONE current tree (owned by the C engine), so you can build
a BST in tab 1 and then edit that same tree by hand in tab 3.

Run:  python bst_gui.py
The C engine (bst_engine.c) is compiled automatically with gcc on first run.
"""
import ctypes
import json
import os
import random
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

HERE = os.path.dirname(os.path.abspath(__file__))
EXT = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
LIB_PATH = os.path.join(HERE, "bst_engine" + EXT)
SRC_PATH = os.path.join(HERE, "bst_engine.c")
MAX_NODES = 127
UNDO_LIMIT = 100


# --------------------------------------------------------------------------
# C engine wrapper
# --------------------------------------------------------------------------
def compile_engine():
    cmd = ["gcc", "-shared", "-O2", "-static-libgcc", "-o", LIB_PATH, SRC_PATH]
    if sys.platform != "win32":
        cmd.insert(2, "-fPIC")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError(
            "gcc was not found.\n\nInstall MinGW-w64 (Windows) or build manually:\n"
            "gcc -shared -O2 -o bst_engine.dll bst_engine.c"
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError("Compilation failed:\n" + e.stderr)


class Engine:
    def __init__(self):
        if (not os.path.exists(LIB_PATH)
                or os.path.getmtime(LIB_PATH) < os.path.getmtime(SRC_PATH)):
            compile_engine()
        lib = ctypes.CDLL(LIB_PATH)
        I, P, IP = ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)

        def sig(fn, args, res):
            f = getattr(lib, fn)
            f.argtypes, f.restype = args, res

        # --- original functions ---
        sig("tree_free", [P], None)
        sig("bst_build", [IP, I], P)
        sig("bst_from_preorder", [IP, I], P)
        sig("bst_from_postorder", [IP, I], P)
        sig("tree_from_in_pre", [IP, IP, I], P)
        sig("tree_from_in_post", [IP, IP, I], P)
        sig("tree_size", [P], I)
        sig("tree_height", [P], I)
        sig("tree_preorder", [P, IP], I)
        sig("tree_inorder", [P, IP], I)
        sig("tree_postorder", [P, IP], I)
        sig("tree_flatten", [P, IP, IP, IP], I)
        # --- editor additions ---
        sig("tree_new_root", [I], P)
        sig("tree_add_child", [P, I, I, I], I)
        sig("tree_set_value", [P, I, I], I)
        sig("tree_delete_subtree", [P, I], P)
        sig("tree_node_depth", [P, I], I)
        sig("tree_clone", [P], P)
        sig("tree_levelorder", [P, IP], I)
        sig("tree_order_idx", [P, I, IP], I)
        sig("tree_stats", [P, IP], None)
        sig("tree_classify", [P, ctypes.c_char_p, I], I)
        sig("tree_from_in_level", [IP, IP, I], P)
        sig("tree_from_arrays", [IP, IP, IP, I], P)
        sig("tree_random", [I, ctypes.c_uint], P)
        self.lib = lib

    @staticmethod
    def _arr(values):
        return (ctypes.c_int * max(1, len(values)))(*values)

    # ----- lifetime -----
    def free(self, root):
        if root:
            self.lib.tree_free(root)

    def clone(self, root):
        return self.lib.tree_clone(root) if root else None

    # ----- building -----
    def build_bst(self, values):
        return self.lib.bst_build(self._arr(values), len(values))

    def from_preorder(self, pre):
        return self.lib.bst_from_preorder(self._arr(pre), len(pre))

    def from_postorder(self, post):
        return self.lib.bst_from_postorder(self._arr(post), len(post))

    def from_in_pre(self, ino, pre):
        return self.lib.tree_from_in_pre(self._arr(ino), self._arr(pre), len(ino))

    def from_in_post(self, ino, post):
        return self.lib.tree_from_in_post(self._arr(ino), self._arr(post), len(ino))

    def from_in_level(self, ino, level):
        return self.lib.tree_from_in_level(self._arr(ino), self._arr(level), len(ino))

    def from_arrays(self, vals, left, right):
        return self.lib.tree_from_arrays(self._arr(vals), self._arr(left),
                                         self._arr(right), len(vals))

    def random_tree(self, n):
        return self.lib.tree_random(n, random.getrandbits(31) | 1)

    def new_root(self, v):
        return self.lib.tree_new_root(v)

    # ----- editing (nodes are addressed by preorder index) -----
    def add_child(self, root, idx, side, v):
        return bool(self.lib.tree_add_child(root, idx, side, v))

    def set_value(self, root, idx, v):
        return bool(self.lib.tree_set_value(root, idx, v))

    def delete_subtree(self, root, idx):
        return self.lib.tree_delete_subtree(root, idx)

    def node_depth(self, root, idx):
        return self.lib.tree_node_depth(root, idx)

    # ----- queries -----
    def size(self, root):
        return self.lib.tree_size(root) if root else 0

    def height(self, root):
        return self.lib.tree_height(root) if root else -1

    def traversals(self, root):
        n = self.size(root)
        out = []
        for fn in (self.lib.tree_preorder, self.lib.tree_inorder,
                   self.lib.tree_postorder, self.lib.tree_levelorder):
            buf = (ctypes.c_int * max(1, n))()
            if n:
                fn(root, buf)
            out.append(list(buf[:n]))
        return out  # [pre, in, post, level]

    def order_indexes(self, root):
        """Visiting orders as node indexes: {'pre','in','post','level'}."""
        n = self.size(root)
        res = {}
        for kind, key in enumerate(("pre", "in", "post", "level")):
            buf = (ctypes.c_int * max(1, n))()
            if n:
                self.lib.tree_order_idx(root, kind, buf)
            res[key] = list(buf[:n])
        return res

    def flatten(self, root):
        n = self.size(root)
        v, l, r = ((ctypes.c_int * max(1, n))() for _ in range(3))
        if n:
            self.lib.tree_flatten(root, v, l, r)
        return list(v[:n]), list(l[:n]), list(r[:n])

    def stats(self, root):
        out = (ctypes.c_int * 6)()
        self.lib.tree_stats(root, out)
        return dict(zip(("nodes", "height", "leaves", "internal", "min", "max"), out))

    def classify(self, root):
        """List of (type name, applies?, reason) computed by the C engine."""
        buf = ctypes.create_string_buffer(8192)
        self.lib.tree_classify(root, buf, 8192)
        rows = []
        for line in buf.value.decode("ascii", "replace").splitlines():
            parts = line.split("\t", 2)
            if len(parts) == 3:
                rows.append((parts[0], parts[1] == "1", parts[2]))
        return rows


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------
def parse_ints(text):
    parts = text.replace(",", " ").split()
    if not parts:
        raise ValueError("Please enter some numbers.")
    try:
        vals = [int(p) for p in parts]
    except ValueError:
        raise ValueError("Only whole numbers separated by commas or spaces, please.")
    if len(vals) > MAX_NODES:
        raise ValueError(f"Maximum {MAX_NODES} nodes.")
    return vals


MODES = [
    "Preorder only (BST)",
    "Postorder only (BST)",
    "Inorder + Preorder",
    "Inorder + Postorder",
    "Inorder + Level-order",
]
MODE_NOTES = {
    MODES[0]: "A BST is fully determined by its preorder sequence alone.",
    MODES[1]: "A BST is fully determined by its postorder sequence alone.",
    MODES[2]: "Works for ANY binary tree with distinct values (not only BSTs).",
    MODES[3]: "Works for ANY binary tree with distinct values (not only BSTs).",
    MODES[4]: "Works for ANY binary tree with distinct values (not only BSTs).",
}
MODE_NEEDS = {
    MODES[0]: {"pre"}, MODES[1]: {"post"},
    MODES[2]: {"in", "pre"}, MODES[3]: {"in", "post"}, MODES[4]: {"in", "level"},
}

NODE_FILL, NODE_ACTIVE, NODE_DONE = "#cfe8ff", "#ffd166", "#9be28f"
NODE_SELECT, SELECT_OUTLINE = "#ffe066", "#d9480f"
NODE_OUTLINE = "#2b6cb0"
EDITOR_TAB = 2


class App(tk.Tk):
    X_GAP, Y_GAP, RAD, MARGIN = 44, 64, 18, 34

    def __init__(self):
        super().__init__()
        self.title("Binary Tree Studio  -  Python GUI + C engine")
        self.geometry("1180x780")
        self.minsize(900, 600)
        self.eng = Engine()
        self.root_ptr = None            # the ONE current tree (owned by the C engine)
        self.undo, self.redo = [], []   # stacks of tree pointers
        self.selected = None            # preorder index of the selected node
        self.items = []                 # node index -> (oval_id, text_id)
        self.orders = {}                # key -> list of values
        self.order_idx = {}             # key -> list of node indexes
        self.anim_job = None
        self.editor_active = False
        self._build_ui()
        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.build_from_values()

    # ---------- UI construction ----------
    def _build_ui(self):
        self.nb = nb = ttk.Notebook(self)
        nb.pack(fill="x", padx=10, pady=(10, 4))
        nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Tab 1: values -> traversals
        t1 = ttk.Frame(nb, padding=10)
        nb.add(t1, text="  Nodes  \u2192  Traversals  ")
        ttk.Label(t1, text="Node values (inserted in this order):").grid(row=0, column=0, sticky="w")
        self.values_var = tk.StringVar(value="50, 30, 70, 20, 40, 60, 80")
        e = ttk.Entry(t1, textvariable=self.values_var, width=60)
        e.grid(row=1, column=0, columnspan=3, sticky="we", pady=4)
        e.bind("<Return>", lambda _e: self.build_from_values())
        ttk.Button(t1, text="Build tree", command=self.build_from_values).grid(row=1, column=3, padx=8)

        ttk.Label(t1, text="Or generate").grid(row=2, column=0, sticky="w", pady=(8, 0))
        rnd = ttk.Frame(t1)
        rnd.grid(row=2, column=1, columnspan=3, sticky="w", pady=(8, 0))
        self.count_var = tk.IntVar(value=8)
        ttk.Spinbox(rnd, from_=1, to=MAX_NODES, textvariable=self.count_var, width=5).pack(side="left")
        ttk.Label(rnd, text="random nodes").pack(side="left", padx=6)
        ttk.Button(rnd, text="Generate", command=self.build_random).pack(side="left")
        t1.columnconfigure(0, weight=1)

        # Tab 2: traversals -> tree
        t2 = ttk.Frame(nb, padding=10)
        nb.add(t2, text="  Traversals  \u2192  Tree  ")
        ttk.Label(t2, text="Given:").grid(row=0, column=0, sticky="w")
        self.mode_var = tk.StringVar(value=MODES[2])
        cb = ttk.Combobox(t2, textvariable=self.mode_var, values=MODES, state="readonly", width=24)
        cb.grid(row=0, column=1, sticky="w", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda _e: self._update_mode())
        self.mode_note = ttk.Label(t2, foreground="#555")
        self.mode_note.grid(row=0, column=2, sticky="w", padx=8)

        self.in_in, self.pre_in, self.post_in, self.level_in = (tk.StringVar() for _ in range(4))
        self.entries = {}
        for r, (key, label, var) in enumerate(
                [("in", "Inorder", self.in_in), ("pre", "Preorder", self.pre_in),
                 ("post", "Postorder", self.post_in), ("level", "Level-order", self.level_in)], start=1):
            ttk.Label(t2, text=label + ":").grid(row=r, column=0, sticky="w", pady=2)
            ent = ttk.Entry(t2, textvariable=var, width=60)
            ent.grid(row=r, column=1, columnspan=2, sticky="we", pady=2, padx=6)
            ent.bind("<Return>", lambda _e: self.reconstruct())
            self.entries[key] = ent
        ttk.Button(t2, text="Reconstruct tree", command=self.reconstruct).grid(row=1, column=3, rowspan=4, padx=8)
        t2.columnconfigure(2, weight=1)
        self._update_mode()

        # Tab 3: interactive editor
        t3 = ttk.Frame(nb, padding=10)
        nb.add(t3, text="  Tree Editor  ")
        self.sel_var = tk.StringVar(value="Selected: none")
        ttk.Label(t3, textvariable=self.sel_var, font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=8, sticky="w")
        ttk.Label(t3, foreground="#555",
                  text="Click a node to select it, then click a dashed + to add a child exactly "
                       "there. Right-click a node for a menu.  Ctrl+Z / Ctrl+Y = undo / redo."
                  ).grid(row=1, column=0, columnspan=8, sticky="w", pady=(0, 6))
        self.btn_root = ttk.Button(t3, text="Create root", command=self.create_root)
        self.btn_left = ttk.Button(t3, text="Add Left Child", command=lambda: self.add_child(0))
        self.btn_right = ttk.Button(t3, text="Add Right Child", command=lambda: self.add_child(1))
        self.btn_edit = ttk.Button(t3, text="Edit value", command=self.edit_value)
        self.btn_del = ttk.Button(t3, text="Delete subtree", command=self.delete_subtree)
        for c, b in enumerate((self.btn_root, self.btn_left, self.btn_right, self.btn_edit, self.btn_del)):
            b.grid(row=2, column=c, padx=(0, 6), sticky="w")
        self.btn_undo = ttk.Button(t3, text="Undo", command=self.do_undo)
        self.btn_redo = ttk.Button(t3, text="Redo", command=self.do_redo)
        self.btn_clear = ttk.Button(t3, text="Clear tree", command=self.clear_tree)
        for c, b in enumerate((self.btn_undo, self.btn_redo, self.btn_clear), start=0):
            b.grid(row=3, column=c, padx=(0, 6), pady=(6, 0), sticky="w")
        ttk.Button(t3, text="Save JSON", command=self.save_json).grid(
            row=3, column=3, padx=(0, 6), pady=(6, 0), sticky="w")
        ttk.Button(t3, text="Load JSON", command=self.load_json).grid(
            row=3, column=4, padx=(0, 6), pady=(6, 0), sticky="w")
        rnd3 = ttk.Frame(t3)
        rnd3.grid(row=3, column=5, columnspan=3, padx=(12, 0), pady=(6, 0), sticky="w")
        self.rcount_var = tk.IntVar(value=10)
        ttk.Spinbox(rnd3, from_=1, to=MAX_NODES, textvariable=self.rcount_var, width=5).pack(side="left")
        ttk.Button(rnd3, text="Random tree", command=self.random_general).pack(side="left", padx=6)

        # Right-click menu
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Add Left Child", command=lambda: self.add_child(0))
        self.menu.add_command(label="Add Right Child", command=lambda: self.add_child(1))
        self.menu.add_command(label="Edit value", command=self.edit_value)
        self.menu.add_separator()
        self.menu.add_command(label="Delete subtree", command=self.delete_subtree)

        # Output panel (shared by all tabs)
        out = ttk.LabelFrame(self, text="Traversals of the current tree", padding=8)
        out.pack(fill="x", padx=10, pady=4)
        self.out_vars = {}
        for r, (key, label) in enumerate([("pre", "Preorder  (Root, L, R)"),
                                          ("in", "Inorder  (L, Root, R)"),
                                          ("post", "Postorder  (L, R, Root)"),
                                          ("level", "Level-order  (by level)")]):
            ttk.Label(out, text=label, width=24).grid(row=r, column=0, sticky="w")
            var = tk.StringVar()
            ttk.Entry(out, textvariable=var, state="readonly").grid(row=r, column=1, sticky="we", pady=2)
            ttk.Button(out, text="\u25B6 Animate", width=10,
                       command=lambda k=key: self.animate(k)).grid(row=r, column=2, padx=(8, 0))
            self.out_vars[key] = var
        out.columnconfigure(1, weight=1)
        self.info_var = tk.StringVar()
        ttk.Label(out, textvariable=self.info_var, foreground="#333").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))

        # Canvas (left) + tree-type panel (right)
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        cf = ttk.Frame(body)
        cf.grid(row=0, column=0, sticky="nsew")
        self.canvas = tk.Canvas(cf, bg="white", highlightthickness=1, highlightbackground="#bbb")
        xs = ttk.Scrollbar(cf, orient="horizontal", command=self.canvas.xview)
        ys = ttk.Scrollbar(cf, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=xs.set, yscrollcommand=ys.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="we")
        cf.rowconfigure(0, weight=1)
        cf.columnconfigure(0, weight=1)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Button-2>", self.on_right_click)   # macOS

        tp = ttk.LabelFrame(body, text="Tree type", padding=6)
        tp.grid(row=0, column=1, sticky="ns", padx=(10, 0))
        self.type_summary = tk.StringVar()
        ttk.Label(tp, textvariable=self.type_summary, font=("Segoe UI", 10, "bold"),
                  wraplength=320, justify="left").pack(anchor="w", pady=(0, 6))
        self.type_text = tk.Text(tp, width=44, height=20, wrap="word", relief="flat",
                                 font=("Segoe UI", 9), state="disabled", bg=self.cget("bg"))
        self.type_text.pack(fill="both", expand=True)
        self.type_text.tag_configure("yes", foreground="#1b7f3b", font=("Segoe UI", 9, "bold"))
        self.type_text.tag_configure("no", foreground="#8a8a8a")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

    def _bind_keys(self):
        self.bind("<Control-z>", self._key_undo)
        self.bind("<Control-y>", self._key_redo)
        self.bind("<Control-Z>", self._key_redo)   # Ctrl+Shift+Z

    def _typing(self):
        return isinstance(self.focus_get(), (ttk.Entry, tk.Entry, ttk.Spinbox, ttk.Combobox))

    def _key_undo(self, _e):
        if not self._typing():
            self.do_undo()

    def _key_redo(self, _e):
        if not self._typing():
            self.do_redo()

    def _on_tab_changed(self, _e):
        self.editor_active = (self.nb.index(self.nb.select()) == EDITOR_TAB)
        if hasattr(self, "canvas") and hasattr(self, "type_text"):
            self.draw()

    def _update_mode(self):
        mode = self.mode_var.get()
        need = MODE_NEEDS[mode]
        for k, ent in self.entries.items():
            ent.configure(state="normal" if k in need else "disabled")
        self.mode_note.configure(text=MODE_NOTES[mode])

    # ---------- Tree ownership / undo ----------
    def _push_undo(self, snapshot):
        self.undo.append(snapshot)
        while len(self.undo) > UNDO_LIMIT:
            self.eng.free(self.undo.pop(0))
        self._clear_redo()

    def _clear_redo(self):
        for p in self.redo:
            self.eng.free(p)
        self.redo.clear()

    def set_tree(self, ptr, note="", keep_selection=False):
        """Replace the current tree (the old one goes on the undo stack)."""
        self._push_undo(self.root_ptr)
        self.root_ptr = ptr
        if not keep_selection:
            self.selected = None
        self.refresh(note)

    def _edit_in_place(self, fn):
        """Snapshot the tree, run fn() which mutates it, undo-able. fn returns
        the new root pointer, or None to signal failure (snapshot discarded)."""
        snap = self.eng.clone(self.root_ptr)
        result = fn()
        if result is False:
            self.eng.free(snap)
            return False
        self._push_undo(snap)
        return True

    def do_undo(self):
        if not self.undo:
            return
        self.redo.append(self.root_ptr)
        self.root_ptr = self.undo.pop()
        self.selected = None
        self.refresh()

    def do_redo(self):
        if not self.redo:
            return
        self.undo.append(self.root_ptr)
        self.root_ptr = self.redo.pop()
        self.selected = None
        self.refresh()

    # ---------- Actions: tab 1 / tab 2 ----------
    def build_from_values(self):
        try:
            vals = parse_ints(self.values_var.get())
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e))
            return
        unique = list(dict.fromkeys(vals))
        note = ""
        if len(unique) != len(vals):
            note = f"  (ignored {len(vals) - len(unique)} duplicate value(s))"
        self.set_tree(self.eng.build_bst(unique), note)

    def build_random(self):
        try:
            n = int(self.count_var.get())
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid input", "Enter a whole number of nodes.")
            return
        n = max(1, min(n, MAX_NODES))
        vals = random.sample(range(1, max(100, 3 * n)), n)
        self.values_var.set(", ".join(map(str, vals)))
        self.set_tree(self.eng.build_bst(vals))

    def reconstruct(self):
        mode = self.mode_var.get()
        try:
            given = {}
            for key, var in (("in", self.in_in), ("pre", self.pre_in),
                             ("post", self.post_in), ("level", self.level_in)):
                if key in MODE_NEEDS[mode]:
                    given[key] = parse_ints(var.get())
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e))
            return
        names = {"in": "inorder", "pre": "preorder", "post": "postorder", "level": "level-order"}
        for key, seq in given.items():
            if len(set(seq)) != len(seq):
                messagebox.showerror("Invalid input", f"The {names[key]} has duplicate values; "
                                                      "values must be distinct.")
                return
        if len({len(s) for s in given.values()}) > 1:
            messagebox.showerror("Invalid input", "All sequences must have the same length.")
            return

        if mode == MODES[0]:
            ptr = self.eng.from_preorder(given["pre"])
        elif mode == MODES[1]:
            ptr = self.eng.from_postorder(given["post"])
        elif mode == MODES[2]:
            ptr = self.eng.from_in_pre(given["in"], given["pre"])
        elif mode == MODES[3]:
            ptr = self.eng.from_in_post(given["in"], given["post"])
        else:
            ptr = self.eng.from_in_level(given["in"], given["level"])

        if not ptr:
            messagebox.showerror("Impossible", "These sequences do not describe any valid tree.")
            return

        # Verify: the rebuilt tree must reproduce every sequence the user gave.
        pre, ino, post, level = self.eng.traversals(ptr)
        actual = {"pre": pre, "in": ino, "post": post, "level": level}
        bad = [names[k] for k, seq in given.items() if actual[k] != seq]
        if bad:
            self.eng.free(ptr)
            what = "BST" if mode in (MODES[0], MODES[1]) else "binary tree"
            messagebox.showerror("Not a valid traversal",
                                 f"The {', '.join(bad)} you gave is not a valid traversal of any {what}.")
            return
        self.set_tree(ptr)

    # ---------- Actions: tab 3 (editor) ----------
    def _ask_value(self, title, initial=None):
        return simpledialog.askinteger(title, "Node value (whole number):", parent=self,
                                       initialvalue=initial, minvalue=-10**9, maxvalue=10**9)

    def create_root(self):
        if self.root_ptr:
            return
        v = self._ask_value("Create root")
        if v is None:
            return
        self.set_tree(self.eng.new_root(v))
        self.selected = 0
        self.refresh()

    def add_child(self, side):
        if not self.root_ptr or self.selected is None:
            return
        vals, L, R = self.eng.flatten(self.root_ptr)
        if (L if side == 0 else R)[self.selected] != -1:
            messagebox.showinfo("Slot taken", "That child slot is already occupied.")
            return
        if len(vals) >= MAX_NODES:
            messagebox.showinfo("Tree is full", f"Maximum {MAX_NODES} nodes.")
            return
        v = self._ask_value("Add left child" if side == 0 else "Add right child")
        if v is None:
            return
        idx = self.selected
        ok = self._edit_in_place(lambda: self.eng.add_child(self.root_ptr, idx, side, v))
        if not ok:
            messagebox.showerror("Error", "Could not add the node.")
            return
        self.refresh()

    def edit_value(self):
        if not self.root_ptr or self.selected is None:
            return
        vals, _, _ = self.eng.flatten(self.root_ptr)
        v = self._ask_value("Edit value", initial=vals[self.selected])
        if v is None or v == vals[self.selected]:
            return
        idx = self.selected
        self._edit_in_place(lambda: self.eng.set_value(self.root_ptr, idx, v))
        self.refresh()

    def delete_subtree(self):
        if not self.root_ptr or self.selected is None:
            return
        idx = self.selected
        vals, L, R = self.eng.flatten(self.root_ptr)
        if idx == 0:
            self.clear_tree()
            return
        # Deleting inside the tree: snapshot, then cut the subtree in place.
        snap = self.eng.clone(self.root_ptr)
        self.root_ptr = self.eng.delete_subtree(self.root_ptr, idx)
        self._push_undo(snap)
        self.selected = None
        self.refresh()

    def clear_tree(self):
        if not self.root_ptr:
            return
        self.set_tree(None)

    def random_general(self):
        try:
            n = int(self.rcount_var.get())
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid input", "Enter a whole number of nodes.")
            return
        n = max(1, min(n, MAX_NODES))
        self.set_tree(self.eng.random_tree(n))

    def save_json(self):
        if not self.root_ptr:
            messagebox.showinfo("Nothing to save", "The tree is empty.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("JSON", "*.json")], title="Save tree")
        if not path:
            return
        vals, L, R = self.eng.flatten(self.root_ptr)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"values": vals, "left": L, "right": R}, f, indent=2)

    def load_json(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")], title="Load tree")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            vals, L, R = data["values"], data["left"], data["right"]
            lists = (vals, L, R)
            if not all(isinstance(x, list) and all(type(i) is int for i in x) for x in lists):
                raise ValueError("values/left/right must be lists of integers")
            if not (len(vals) == len(L) == len(R)) or not vals:
                raise ValueError("the three lists must be non-empty and equally long")
            if len(vals) > MAX_NODES:
                raise ValueError(f"maximum {MAX_NODES} nodes")
        except (OSError, ValueError, KeyError, TypeError) as e:
            messagebox.showerror("Cannot load", f"Not a valid tree file: {e}")
            return
        ptr = self.eng.from_arrays(vals, L, R)
        if not ptr:
            messagebox.showerror("Cannot load", "The file does not describe one valid binary tree.")
            return
        self.set_tree(ptr)

    # ---------- Refresh everything from the engine ----------
    def refresh(self, note=""):
        self._stop_anim()
        ptr = self.root_ptr
        pre, ino, post, level = self.eng.traversals(ptr)
        n = len(ino)
        if self.selected is not None and self.selected >= n:
            self.selected = None
        self.orders = {"pre": pre, "in": ino, "post": post, "level": level}
        self.order_idx = self.eng.order_indexes(ptr)
        for k, seq in self.orders.items():
            self.out_vars[k].set(", ".join(map(str, seq)))

        if n == 0:
            self.info_var.set("Empty tree" + note)
        else:
            st = self.eng.stats(ptr)
            text = (f"Nodes: {st['nodes']}    Height: {st['height']}    Leaves: {st['leaves']}    "
                    f"Internal: {st['internal']}    Min: {st['min']}    Max: {st['max']}")
            if self.selected is not None:
                text += f"    Selected depth: {self.eng.node_depth(ptr, self.selected)}"
            self.info_var.set(text + note)

        self._update_type_panel()
        self._update_buttons()
        self.draw()

    def _update_type_panel(self):
        rows = self.eng.classify(self.root_ptr)
        yes = [name for name, ok, _ in rows if ok and name not in ("Single node", "Empty tree")]
        special = [name for name, ok, _ in rows if ok and name in ("Single node", "Empty tree")]
        self.type_summary.set((", ".join(special + yes)) or "Not a special tree type")
        t = self.type_text
        t.configure(state="normal")
        t.delete("1.0", "end")
        for name, ok, reason in rows:
            if ok:
                t.insert("end", f"\u2714 {name}", "yes")
                t.insert("end", f" \u2014 {reason}\n")
            else:
                t.insert("end", f"\u2718 Not {name}: {reason}\n", "no")
        t.configure(state="disabled")

    def _update_buttons(self):
        has_tree = self.root_ptr is not None
        sel = self.selected
        left_free = right_free = False
        if has_tree and sel is not None:
            _, L, R = self.eng.flatten(self.root_ptr)
            left_free, right_free = L[sel] == -1, R[sel] == -1
        en = lambda b, flag: b.configure(state="normal" if flag else "disabled")
        en(self.btn_root, not has_tree)
        en(self.btn_left, left_free)
        en(self.btn_right, right_free)
        en(self.btn_edit, sel is not None)
        en(self.btn_del, sel is not None)
        en(self.btn_undo, bool(self.undo))
        en(self.btn_redo, bool(self.redo))
        en(self.btn_clear, has_tree)
        if sel is None:
            self.sel_var.set("Selected: none")
        else:
            vals, _, _ = self.eng.flatten(self.root_ptr)
            self.sel_var.set(f"Selected: node with value {vals[sel]}  "
                             f"(depth {self.eng.node_depth(self.root_ptr, sel)})")
        self.menu.entryconfigure(0, state="normal" if left_free else "disabled")
        self.menu.entryconfigure(1, state="normal" if right_free else "disabled")

    # ---------- Drawing ----------
    def draw(self):
        c = self.canvas
        c.delete("all")
        self.items = []
        if not self.root_ptr:
            c.configure(scrollregion=(0, 0, 1, 1))
            msg = ("Empty tree - click 'Create root' in the Tree Editor tab"
                   if self.editor_active else "Empty tree")
            c.create_text(20, 20, anchor="nw", text=msg, fill="#777", font=("Segoe UI", 11))
            return
        vals, L, R = self.eng.flatten(self.root_ptr)
        pos, counter = {}, [0]

        def walk(i, depth):
            if i < 0:
                return
            walk(L[i], depth + 1)
            pos[i] = (counter[0], depth)
            counter[0] += 1
            walk(R[i], depth + 1)

        walk(0, 0)
        max_depth = max(d for _, d in pos.values())
        need_w = (len(vals) - 1) * self.X_GAP + 2 * self.MARGIN
        need_h = (max_depth + 1) * self.Y_GAP + 2 * self.MARGIN   # +1 level: room for "+" slots
        self.update_idletasks()
        offset = max(0, (c.winfo_width() - need_w) // 2)

        def xy(i):
            gx, d = pos[i]
            return offset + self.MARGIN + gx * self.X_GAP, self.MARGIN + d * self.Y_GAP

        for i in range(len(vals)):
            x, y = xy(i)
            for ch in (L[i], R[i]):
                if ch >= 0:
                    cx, cy = xy(ch)
                    c.create_line(x, y, cx, cy, width=2, fill="#888")
        r = self.RAD
        for i, v in enumerate(vals):
            x, y = xy(i)
            oval = c.create_oval(x - r, y - r, x + r, y + r, fill=NODE_FILL,
                                 outline=NODE_OUTLINE, width=2, tags=("node", f"node:{i}"))
            text = c.create_text(x, y, text=str(v), font=("Segoe UI", 10, "bold"),
                                 tags=("node", f"node:{i}"))
            self.items.append((oval, text))

        # Free child slots of the selected node: dashed "+" circles
        if self.editor_active and self.selected is not None:
            i = self.selected
            x, y = xy(i)
            for side, child in ((0, L[i]), (1, R[i])):
                if child != -1:
                    continue
                sx = x + (-1 if side == 0 else 1) * self.X_GAP * 0.5
                sy = y + self.Y_GAP
                tag = f"slot:{i}:{side}"
                c.create_line(x, y, sx, sy, dash=(3, 3), fill=NODE_OUTLINE, tags=(tag,))
                c.create_oval(sx - 9, sy - 9, sx + 9, sy + 9, fill="white", outline=NODE_OUTLINE,
                              dash=(3, 2), width=2, tags=("slot", tag))
                c.create_text(sx, sy, text="+", fill=NODE_OUTLINE, font=("Segoe UI", 11, "bold"),
                              tags=("slot", tag))
        self._paint()
        c.configure(scrollregion=(0, 0, max(need_w + offset, c.winfo_width()),
                                  max(need_h, c.winfo_height())))

    def _paint(self):
        """Default colours, with the selected node highlighted."""
        for i, (oval, _) in enumerate(self.items):
            if i == self.selected:
                self.canvas.itemconfig(oval, fill=NODE_SELECT, outline=SELECT_OUTLINE, width=3)
            else:
                self.canvas.itemconfig(oval, fill=NODE_FILL, outline=NODE_OUTLINE, width=2)

    # ---------- Mouse ----------
    def _tags_at_cursor(self):
        cur = self.canvas.find_withtag("current")
        return self.canvas.gettags(cur[0]) if cur else ()

    def on_click(self, _event):
        for tag in self._tags_at_cursor():
            if tag.startswith("slot:"):
                _, idx, side = tag.split(":")
                self.selected = int(idx)
                self.add_child(int(side))
                return
            if tag.startswith("node:"):
                self.selected = int(tag.split(":")[1])
                self.refresh_selection()
                return
        self.selected = None
        self.refresh_selection()

    def on_right_click(self, event):
        for tag in self._tags_at_cursor():
            if tag.startswith("node:"):
                self.selected = int(tag.split(":")[1])
                self.refresh_selection()
                self.menu.tk_popup(event.x_root, event.y_root)
                self.menu.grab_release()
                return

    def refresh_selection(self):
        """Selection changed: update labels/buttons and redraw (slots move)."""
        self._stop_anim()
        if self.root_ptr:
            st = self.eng.stats(self.root_ptr)
            text = (f"Nodes: {st['nodes']}    Height: {st['height']}    Leaves: {st['leaves']}    "
                    f"Internal: {st['internal']}    Min: {st['min']}    Max: {st['max']}")
            if self.selected is not None:
                text += f"    Selected depth: {self.eng.node_depth(self.root_ptr, self.selected)}"
            self.info_var.set(text)
        self._update_buttons()
        self.draw()

    # ---------- Animation ----------
    def _stop_anim(self):
        if self.anim_job is not None:
            self.after_cancel(self.anim_job)
            self.anim_job = None

    def animate(self, key):
        if not self.root_ptr:
            return
        self._stop_anim()
        self._paint()
        seq = self.order_idx[key]

        def step(i):
            if i > 0:
                self.canvas.itemconfig(self.items[seq[i - 1]][0], fill=NODE_DONE)
            if i < len(seq):
                self.canvas.itemconfig(self.items[seq[i]][0], fill=NODE_ACTIVE)
                self.anim_job = self.after(500, step, i + 1)
            else:
                self.anim_job = None

        step(0)

    def _close(self):
        self._stop_anim()
        for p in [self.root_ptr] + self.undo + self.redo:
            self.eng.free(p)
        self.root_ptr = None
        self.undo.clear()
        self.redo.clear()
        self.destroy()


if __name__ == "__main__":
    try:
        App().mainloop()
    except RuntimeError as err:
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("Engine error", str(err))
