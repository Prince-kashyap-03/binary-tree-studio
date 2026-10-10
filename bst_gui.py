"""
bst_gui.py - Binary Search Tree visualizer (Python GUI + C engine)

Run:  python bst_gui.py
The C engine (bst_engine.c) is compiled automatically with gcc on first run.
"""
import ctypes
import os
import random
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox

HERE = os.path.dirname(os.path.abspath(__file__))
EXT = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
LIB_PATH = os.path.join(HERE, "bst_engine" + EXT)
SRC_PATH = os.path.join(HERE, "bst_engine.c")
MAX_NODES = 127


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
        self.lib = lib

    @staticmethod
    def _arr(values):
        return (ctypes.c_int * max(1, len(values)))(*values)

    def free(self, root):
        if root:
            self.lib.tree_free(root)

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

    def size(self, root):
        return self.lib.tree_size(root)

    def height(self, root):
        return self.lib.tree_height(root)

    def traversals(self, root):
        n = self.size(root)
        out = []
        for fn in (self.lib.tree_preorder, self.lib.tree_inorder, self.lib.tree_postorder):
            buf = (ctypes.c_int * max(1, n))()
            fn(root, buf)
            out.append(list(buf[:n]))
        return out  # [pre, in, post]

    def flatten(self, root):
        n = self.size(root)
        v, l, r = ((ctypes.c_int * max(1, n))() for _ in range(3))
        self.lib.tree_flatten(root, v, l, r)
        return list(v[:n]), list(l[:n]), list(r[:n])


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
]
MODE_NOTES = {
    MODES[0]: "A BST is fully determined by its preorder sequence alone.",
    MODES[1]: "A BST is fully determined by its postorder sequence alone.",
    MODES[2]: "Works for ANY binary tree with distinct values (not only BSTs).",
    MODES[3]: "Works for ANY binary tree with distinct values (not only BSTs).",
}

NODE_FILL, NODE_ACTIVE, NODE_DONE = "#cfe8ff", "#ffd166", "#9be28f"


class App(tk.Tk):
    X_GAP, Y_GAP, RAD, MARGIN = 44, 64, 18, 34

    def __init__(self):
        super().__init__()
        self.title("BST Visualizer  -  Python GUI + C engine")
        self.geometry("980x720")
        self.minsize(760, 560)
        self.eng = Engine()
        self.root_ptr = None
        self.items = {}      # value -> (oval_id, text_id)
        self.orders = {}     # "pre"/"in"/"post" -> list of values
        self.anim_job = None
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.build_from_values()

    # ---------- UI construction ----------
    def _build_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="x", padx=10, pady=(10, 4))

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

        self.in_in, self.pre_in, self.post_in = (tk.StringVar() for _ in range(3))
        self.entries = {}
        for r, (key, label, var) in enumerate(
                [("in", "Inorder", self.in_in), ("pre", "Preorder", self.pre_in),
                 ("post", "Postorder", self.post_in)], start=1):
            ttk.Label(t2, text=label + ":").grid(row=r, column=0, sticky="w", pady=2)
            ent = ttk.Entry(t2, textvariable=var, width=60)
            ent.grid(row=r, column=1, columnspan=2, sticky="we", pady=2, padx=6)
            ent.bind("<Return>", lambda _e: self.reconstruct())
            self.entries[key] = ent
        ttk.Button(t2, text="Reconstruct tree", command=self.reconstruct).grid(row=1, column=3, rowspan=3, padx=8)
        t2.columnconfigure(2, weight=1)
        self._update_mode()

        # Output panel
        out = ttk.LabelFrame(self, text="Traversals of the current tree", padding=8)
        out.pack(fill="x", padx=10, pady=4)
        self.out_vars = {}
        for r, (key, label) in enumerate([("pre", "Preorder  (Root, L, R)"),
                                          ("in", "Inorder  (L, Root, R)"),
                                          ("post", "Postorder  (L, R, Root)")]):
            ttk.Label(out, text=label, width=24).grid(row=r, column=0, sticky="w")
            var = tk.StringVar()
            ttk.Entry(out, textvariable=var, state="readonly").grid(row=r, column=1, sticky="we", pady=2)
            ttk.Button(out, text="\u25B6 Animate", width=10,
                       command=lambda k=key: self.animate(k)).grid(row=r, column=2, padx=(8, 0))
            self.out_vars[key] = var
        out.columnconfigure(1, weight=1)
        self.info_var = tk.StringVar()
        ttk.Label(out, textvariable=self.info_var, foreground="#333").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))

        # Canvas
        cf = ttk.Frame(self)
        cf.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        self.canvas = tk.Canvas(cf, bg="white", highlightthickness=1, highlightbackground="#bbb")
        xs = ttk.Scrollbar(cf, orient="horizontal", command=self.canvas.xview)
        ys = ttk.Scrollbar(cf, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=xs.set, yscrollcommand=ys.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="we")
        cf.rowconfigure(0, weight=1)
        cf.columnconfigure(0, weight=1)

    def _update_mode(self):
        mode = self.mode_var.get()
        need = {MODES[0]: {"pre"}, MODES[1]: {"post"},
                MODES[2]: {"in", "pre"}, MODES[3]: {"in", "post"}}[mode]
        for k, ent in self.entries.items():
            ent.configure(state="normal" if k in need else "disabled")
        self.mode_note.configure(text=MODE_NOTES[mode])

    # ---------- Actions ----------
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
            if mode in (MODES[2], MODES[3]):
                given["in"] = parse_ints(self.in_in.get())
            if mode in (MODES[0], MODES[2]):
                given["pre"] = parse_ints(self.pre_in.get())
            if mode in (MODES[1], MODES[3]):
                given["post"] = parse_ints(self.post_in.get())
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e))
            return
        for name, seq in given.items():
            if len(set(seq)) != len(seq):
                messagebox.showerror("Invalid input", f"The {name}order has duplicate values; "
                                                      "values must be distinct.")
                return
        if len(given) == 2 and len(given["in"]) != len(next(v for k, v in given.items() if k != "in")):
            messagebox.showerror("Invalid input", "Both sequences must have the same length.")
            return

        if mode == MODES[0]:
            ptr = self.eng.from_preorder(given["pre"])
        elif mode == MODES[1]:
            ptr = self.eng.from_postorder(given["post"])
        elif mode == MODES[2]:
            ptr = self.eng.from_in_pre(given["in"], given["pre"])
        else:
            ptr = self.eng.from_in_post(given["in"], given["post"])

        if not ptr:
            messagebox.showerror("Impossible", "These sequences do not describe any valid tree.")
            return

        # Verify: the rebuilt tree must reproduce every sequence the user gave.
        pre, ino, post = self.eng.traversals(ptr)
        actual = {"pre": pre, "in": ino, "post": post}
        bad = [k for k, seq in given.items() if actual[k] != seq]
        if bad:
            self.eng.free(ptr)
            what = "BST" if mode in (MODES[0], MODES[1]) else "binary tree"
            messagebox.showerror("Not a valid traversal",
                                 f"The {', '.join(bad)}order you gave is not a valid traversal of any {what}.")
            return
        self.set_tree(ptr)

    def set_tree(self, ptr, note=""):
        self._stop_anim()
        if self.root_ptr:
            self.eng.free(self.root_ptr)
        self.root_ptr = ptr
        pre, ino, post = self.eng.traversals(ptr)
        self.orders = {"pre": pre, "in": ino, "post": post}
        for k, seq in self.orders.items():
            self.out_vars[k].set(", ".join(map(str, seq)))
        is_bst = ino == sorted(ino)
        self.info_var.set(f"Nodes: {len(ino)}    Height: {self.eng.height(ptr)}    "
                          f"Valid BST: {'yes' if is_bst else 'no'}{note}")
        self.draw()

    # ---------- Drawing ----------
    def draw(self):
        c = self.canvas
        c.delete("all")
        self.items.clear()
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
        need_h = max_depth * self.Y_GAP + 2 * self.MARGIN
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
        for i, v in enumerate(vals):
            x, y = xy(i)
            r = self.RAD
            oval = c.create_oval(x - r, y - r, x + r, y + r, fill=NODE_FILL, outline="#2b6cb0", width=2)
            text = c.create_text(x, y, text=str(v), font=("Segoe UI", 10, "bold"))
            self.items[v] = (oval, text)
        c.configure(scrollregion=(0, 0, max(need_w + offset, c.winfo_width()),
                                  max(need_h, c.winfo_height())))

    # ---------- Animation ----------
    def _stop_anim(self):
        if self.anim_job is not None:
            self.after_cancel(self.anim_job)
            self.anim_job = None

    def _reset_colors(self):
        for oval, _ in self.items.values():
            self.canvas.itemconfig(oval, fill=NODE_FILL)

    def animate(self, key):
        if not self.root_ptr:
            return
        self._stop_anim()
        self._reset_colors()
        seq = self.orders[key]

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
        if self.root_ptr:
            self.eng.free(self.root_ptr)
            self.root_ptr = None
        self.destroy()


if __name__ == "__main__":
    try:
        App().mainloop()
    except RuntimeError as err:
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("Engine error", str(err))
