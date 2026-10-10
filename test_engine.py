"""
test_engine.py - headless tests for bst_engine.c (no GUI needed).

Run:  python test_engine.py
Compiles the engine with gcc if needed, then checks traversals, tree-type
detection, editing, reconstruction round trips and JSON-style loading.
"""
import ctypes
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXT = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
LIB = os.path.join(HERE, "bst_engine" + EXT)
SRC = os.path.join(HERE, "bst_engine.c")

if not os.path.exists(LIB) or os.path.getmtime(LIB) < os.path.getmtime(SRC):
    cmd = ["gcc", "-shared", "-O2", "-static-libgcc", "-o", LIB, SRC]
    if sys.platform != "win32":
        cmd.insert(2, "-fPIC")
    subprocess.run(cmd, check=True)

lib = ctypes.CDLL(LIB)
I, P, IP = ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)
for name, args, res in [
    ("tree_free", [P], None), ("bst_build", [IP, I], P),
    ("bst_from_preorder", [IP, I], P), ("bst_from_postorder", [IP, I], P),
    ("tree_from_in_pre", [IP, IP, I], P), ("tree_from_in_post", [IP, IP, I], P),
    ("tree_from_in_level", [IP, IP, I], P), ("tree_from_arrays", [IP, IP, IP, I], P),
    ("tree_size", [P], I), ("tree_height", [P], I),
    ("tree_preorder", [P, IP], I), ("tree_inorder", [P, IP], I),
    ("tree_postorder", [P, IP], I), ("tree_levelorder", [P, IP], I),
    ("tree_flatten", [P, IP, IP, IP], I), ("tree_new_root", [I], P),
    ("tree_add_child", [P, I, I, I], I), ("tree_set_value", [P, I, I], I),
    ("tree_delete_subtree", [P, I], P), ("tree_node_depth", [P, I], I),
    ("tree_clone", [P], P), ("tree_order_idx", [P, I, IP], I),
    ("tree_stats", [P, IP], None), ("tree_classify", [P, ctypes.c_char_p, I], I),
    ("tree_random", [I, ctypes.c_uint], P),
]:
    f = getattr(lib, name)
    f.argtypes, f.restype = args, res


def arr(v):
    return (ctypes.c_int * max(1, len(v)))(*v)


def trav(root):
    n = lib.tree_size(root) if root else 0
    out = []
    for fn in (lib.tree_preorder, lib.tree_inorder, lib.tree_postorder, lib.tree_levelorder):
        b = (ctypes.c_int * max(1, n))()
        if n:
            fn(root, b)
        out.append(list(b[:n]))
    return out


def flat(root):
    n = lib.tree_size(root) if root else 0
    v, l, r = ((ctypes.c_int * max(1, n))() for _ in range(3))
    if n:
        lib.tree_flatten(root, v, l, r)
    return list(v[:n]), list(l[:n]), list(r[:n])


def types(root):
    buf = ctypes.create_string_buffer(8192)
    lib.tree_classify(root, buf, 8192)
    res = {}
    for line in buf.value.decode().splitlines():
        name, ok, why = line.split("\t", 2)
        res[name] = (ok == "1", why)
    return res


def from_flat(vals, L, R):
    return lib.tree_from_arrays(arr(vals), arr(L), arr(R), len(vals))


def yes(root):
    return {k for k, (ok, _) in types(root).items() if ok}


passed = 0


def check(cond, msg):
    global passed
    if not cond:
        print("FAIL:", msg)
        sys.exit(1)
    passed += 1


# ---------------- traversals on a known tree ----------------
t = lib.bst_build(arr([50, 30, 70, 20, 40, 60, 80]), 7)
check(trav(t) == [[50, 30, 20, 40, 70, 60, 80], [20, 30, 40, 50, 60, 70, 80],
                  [20, 40, 30, 60, 80, 70, 50], [50, 30, 70, 20, 40, 60, 80]], "traversals of sample BST")
check(lib.tree_height(t) == 2, "height")
st = (ctypes.c_int * 6)()
lib.tree_stats(t, st)
check(list(st) == [7, 2, 4, 3, 20, 80], "stats")
check({"Full", "Perfect", "Complete", "Height-balanced", "Binary Search Tree"} <= yes(t), "perfect BST types")
check("Degenerate (skewed)" not in yes(t), "perfect tree is not degenerate")
for kind, key in enumerate(("pre", "in", "post", "level")):
    b = (ctypes.c_int * 7)()
    lib.tree_order_idx(t, kind, b)
    vals = flat(t)[0]
    check([vals[i] for i in b] == trav(t)[kind], f"order indexes match values ({key})")
lib.tree_free(t)

# ---------------- hand-built type examples (via flat arrays) ----------------
def tree(vals, L, R):
    r = from_flat(vals, L, R)
    check(bool(r), "tree_from_arrays")
    return r

# empty
b = ctypes.create_string_buffer(256); lib.tree_classify(None, b, 256)
check(b.value.startswith(b"Empty tree\t1"), "empty tree")
# single node
s = lib.tree_new_root(5)
check({"Single node", "Full", "Perfect", "Complete", "Height-balanced", "Binary Search Tree",
       "Degenerate (skewed)", "Min-Heap", "Max-Heap"} <= yes(s), "single node is everything")
lib.tree_free(s)
# right-skewed 1->2->3
r = tree([1, 2, 3], [-1, -1, -1], [1, 2, -1])
y = yes(r)
check("Degenerate (skewed)" in y and "right-skewed" in types(r)["Degenerate (skewed)"][1], "right-skewed")
check("Full" not in y and "Complete" not in y and "Height-balanced" not in y and "Binary Search Tree" in y, "skewed types")
lib.tree_free(r)
# left-skewed 3,2,1 and zig-zag
r = tree([3, 2, 1], [1, 2, -1], [-1, -1, -1]); check("left-skewed" in types(r)["Degenerate (skewed)"][1], "left-skewed"); lib.tree_free(r)
r = tree([1, 2, 3], [1, -1, -1], [-1, 2, -1]); check("zig-zag" in types(r)["Degenerate (skewed)"][1], "zig-zag"); lib.tree_free(r)
# complete but not full: 1; 2,3; 4 (left of 2)
r = tree([1, 2, 4, 3], [1, 2, -1, -1], [3, -1, -1, -1])
y = yes(r)
check("Complete" in y and "Full" not in y and "Perfect" not in y and "Height-balanced" in y, "complete-but-not-full")
lib.tree_free(r)
# full but not complete: root with children A(leaf) and B(with 2 leaves)
r = tree([1, 2, 3, 4, 5], [1, -1, 3, -1, -1], [2, -1, 4, -1, -1])
y = yes(r)
check("Full" in y and "Complete" not in y and "Perfect" not in y, "full-but-not-complete")
lib.tree_free(r)
# min heap / max heap
r = tree([1, 2, 3], [1, -1, -1], [2, -1, -1]); check("Min-Heap" in yes(r) and "Max-Heap" not in yes(r), "min-heap"); lib.tree_free(r)
r = tree([9, 5, 3], [1, -1, -1], [2, -1, -1]); check("Max-Heap" in yes(r) and "Min-Heap" not in yes(r), "max-heap"); lib.tree_free(r)
# not a BST (duplicate), not balanced
r = tree([2, 2, 3], [1, -1, -1], [2, -1, -1])
check("Binary Search Tree" not in yes(r) and "duplicate" in types(r)["Binary Search Tree"][1], "duplicate breaks BST")
lib.tree_free(r)
r = tree([1, 2, 3, 4], [1, 2, 3, -1], [-1, -1, -1, -1])
check("Height-balanced" not in yes(r), "unbalanced chain"); lib.tree_free(r)

# ---------------- editing ----------------
r = lib.tree_new_root(10)
check(lib.tree_add_child(r, 0, 0, 5) == 1 and lib.tree_add_child(r, 0, 1, 15) == 1, "add children")
check(lib.tree_add_child(r, 0, 0, 7) == 0, "slot taken refused")
check(lib.tree_add_child(r, 9, 0, 7) == 0, "bad index refused")
check(lib.tree_add_child(r, 1, 1, 7) == 1 and trav(r)[0] == [10, 5, 7, 15], "grandchild goes where asked")
check(lib.tree_node_depth(r, 2) == 2 and lib.tree_node_depth(r, 99) == -1, "depth")
check(lib.tree_set_value(r, 2, 8) == 1 and trav(r)[0] == [10, 5, 8, 15], "set value")
cl = lib.tree_clone(r)
r = lib.tree_delete_subtree(r, 1)
check(trav(r)[0] == [10, 15] and trav(cl)[0] == [10, 5, 8, 15], "delete subtree leaves the clone intact")
r = lib.tree_delete_subtree(r, 0)
check(not r, "deleting root empties the tree")
lib.tree_free(cl)

# ---------------- reconstruction round trips ----------------
random.seed(7)
for _ in range(200):
    n = random.randint(1, 40)
    g = lib.tree_random(n, random.getrandbits(31) | 1)
    p, i, q, lv = trav(g)
    check(len(p) == n and len(set(p)) == n, "random tree has n distinct nodes")
    for fn, args in ((lib.tree_from_in_pre, (i, p)), (lib.tree_from_in_post, (i, q)),
                     (lib.tree_from_in_level, (i, lv))):
        rebuilt = fn(arr(args[0]), arr(args[1]), n)
        check(trav(rebuilt) == [p, i, q, lv], "general rebuild round trip")
        lib.tree_free(rebuilt)
    v, L, R = flat(g)
    copy = from_flat(v, L, R)
    check(trav(copy) == [p, i, q, lv], "flatten -> from_arrays round trip")
    lib.tree_free(copy); lib.tree_free(g)
    vals = random.sample(range(100), n)
    b = lib.bst_build(arr(vals), n)
    p, i, q, lv = trav(b)
    for rebuilt in (lib.bst_from_preorder(arr(p), n), lib.bst_from_postorder(arr(q), n)):
        check(trav(rebuilt) == [p, i, q, lv], "BST rebuild round trip")
        lib.tree_free(rebuilt)
    lib.tree_free(b)

# ---------------- invalid input is rejected, not crashed on ----------------
check(not lib.tree_from_in_pre(arr([1, 2, 3]), arr([9, 8, 7]), 3), "bad in+pre rejected")
check(not lib.tree_from_in_level(arr([1, 2, 3]), arr([9, 8, 7]), 3), "bad in+level rejected")
# A level-order that no tree can produce: the engine builds *something*, but its
# level-order differs from the input - the GUI catches this by re-checking.
x = lib.tree_from_in_level(arr([1, 2, 3, 4]), arr([2, 4, 1, 3]), 4)
check(bool(x) and trav(x)[3] != [2, 4, 1, 3], "inconsistent level-order is detectable")
lib.tree_free(x)
check(not from_flat([1, 2], [1, 0], [-1, -1]), "cyclic arrays rejected")
check(not from_flat([1, 2, 3], [1, -1, -1], [1, -1, -1]), "node with two parents rejected")
check(not from_flat([1, 2, 3], [1, -1, -1], [-1, -1, -1]), "unreachable node rejected")
check(not from_flat([1, 2], [5, -1], [-1, -1]), "out-of-range child rejected")

print(f"All {passed} checks passed.")
