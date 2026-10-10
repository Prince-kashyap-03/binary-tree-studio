/*
 * bst_engine.c - Binary tree engine (called from Python via ctypes)
 *
 * Part 1: BST build, traversals, reconstruction, flatten (original).
 * Part 2 (bottom of file): general binary-tree editor, level-order, tree-type
 *         detection, statistics, clone, JSON-friendly arrays, random trees.
 *
 * Build (Windows, MinGW-w64 gcc):  gcc -shared -O2 -o bst_engine.dll bst_engine.c
 * Build (Linux):                   gcc -shared -fPIC -O2 -o bst_engine.so bst_engine.c
 * Build (macOS):                   gcc -shared -fPIC -O2 -o bst_engine.dylib bst_engine.c
 */
#include <stdlib.h>
#include <stdio.h>
#include <stdarg.h>

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

typedef struct Node {
    int val;
    struct Node *left, *right;
} Node;

static Node *new_node(int v) {
    Node *n = (Node *)malloc(sizeof(Node));
    if (!n) return NULL;
    n->val = v;
    n->left = n->right = NULL;
    return n;
}

/* ---------- BST insert (duplicates are ignored) ---------- */
static Node *insert(Node *root, int v) {
    if (!root) return new_node(v);
    Node *cur = root;
    while (1) {
        if (v < cur->val) {
            if (!cur->left) { cur->left = new_node(v); break; }
            cur = cur->left;
        } else if (v > cur->val) {
            if (!cur->right) { cur->right = new_node(v); break; }
            cur = cur->right;
        } else {
            break; /* duplicate */
        }
    }
    return root;
}

EXPORT void tree_free(Node *root) {
    if (!root) return;
    tree_free(root->left);
    tree_free(root->right);
    free(root);
}

/* Build a BST by inserting values in the given order. */
EXPORT Node *bst_build(const int *vals, int n) {
    Node *root = NULL;
    for (int i = 0; i < n; i++) root = insert(root, vals[i]);
    return root;
}

/* ---------- Traversals ---------- */
EXPORT int tree_size(Node *root) {
    if (!root) return 0;
    return 1 + tree_size(root->left) + tree_size(root->right);
}

EXPORT int tree_height(Node *root) { /* edges; empty tree = -1 */
    if (!root) return -1;
    int l = tree_height(root->left), r = tree_height(root->right);
    return 1 + (l > r ? l : r);
}

static void pre(Node *t, int *out, int *k) {
    if (!t) return;
    out[(*k)++] = t->val;
    pre(t->left, out, k);
    pre(t->right, out, k);
}
static void in(Node *t, int *out, int *k) {
    if (!t) return;
    in(t->left, out, k);
    out[(*k)++] = t->val;
    in(t->right, out, k);
}
static void post(Node *t, int *out, int *k) {
    if (!t) return;
    post(t->left, out, k);
    post(t->right, out, k);
    out[(*k)++] = t->val;
}

/* Each fills `out` (must hold tree_size(root) ints) and returns the count. */
EXPORT int tree_preorder(Node *root, int *out)  { int k = 0; pre(root, out, &k);  return k; }
EXPORT int tree_inorder(Node *root, int *out)   { int k = 0; in(root, out, &k);   return k; }
EXPORT int tree_postorder(Node *root, int *out) { int k = 0; post(root, out, &k); return k; }

/* ---------- Reconstruction ---------- */

/* BST from preorder: inserting the sequence in order recreates the tree. */
EXPORT Node *bst_from_preorder(const int *p, int n) {
    return bst_build(p, n);
}

/* BST from postorder: the reverse of postorder is (root, right, left),
 * so inserting from the END of the sequence recreates the tree. */
EXPORT Node *bst_from_postorder(const int *p, int n) {
    Node *root = NULL;
    for (int i = n - 1; i >= 0; i--) root = insert(root, p[i]);
    return root;
}

/* General binary tree from inorder + preorder (distinct values).
 * Returns NULL if the two sequences are inconsistent. */
static Node *build_ip(const int *io, int lo, int hi, const int *po,
                      int n, int *pi, int *fail) {
    if (lo > hi || *fail) return NULL;
    if (*pi >= n) { *fail = 1; return NULL; }
    int v = po[(*pi)++];
    int k = -1;
    for (int i = lo; i <= hi; i++) if (io[i] == v) { k = i; break; }
    if (k < 0) { *fail = 1; return NULL; }
    Node *root = new_node(v);
    if (!root) { *fail = 1; return NULL; }
    root->left  = build_ip(io, lo, k - 1, po, n, pi, fail);
    root->right = build_ip(io, k + 1, hi, po, n, pi, fail);
    return root;
}

EXPORT Node *tree_from_in_pre(const int *io, const int *po, int n) {
    int pi = 0, fail = 0;
    Node *r = build_ip(io, 0, n - 1, po, n, &pi, &fail);
    if (fail) { tree_free(r); return NULL; }
    return r;
}

/* General binary tree from inorder + postorder (distinct values). */
static Node *build_iq(const int *io, int lo, int hi, const int *qo,
                      int *qi, int *fail) {
    if (lo > hi || *fail) return NULL;
    if (*qi < 0) { *fail = 1; return NULL; }
    int v = qo[(*qi)--];
    int k = -1;
    for (int i = lo; i <= hi; i++) if (io[i] == v) { k = i; break; }
    if (k < 0) { *fail = 1; return NULL; }
    Node *root = new_node(v);
    if (!root) { *fail = 1; return NULL; }
    /* postorder read backwards is root, right, left -> build right first */
    root->right = build_iq(io, k + 1, hi, qo, qi, fail);
    root->left  = build_iq(io, lo, k - 1, qo, qi, fail);
    return root;
}

EXPORT Node *tree_from_in_post(const int *io, const int *qo, int n) {
    int qi = n - 1, fail = 0;
    Node *r = build_iq(io, 0, n - 1, qo, &qi, &fail);
    if (fail) { tree_free(r); return NULL; }
    return r;
}

/* ---------- Flatten for drawing ----------
 * Fills parallel arrays (each of size tree_size). Root is index 0;
 * left/right hold child indices or -1. Returns node count. */
static int flat(Node *t, int *vals, int *L, int *R, int *cnt) {
    if (!t) return -1;
    int me = (*cnt)++;
    vals[me] = t->val;
    L[me] = flat(t->left, vals, L, R, cnt);
    R[me] = flat(t->right, vals, L, R, cnt);
    return me;
}

EXPORT int tree_flatten(Node *root, int *vals, int *L, int *R) {
    int cnt = 0;
    flat(root, vals, L, R, &cnt);
    return cnt;
}


/* =====================================================================
 *  PART 2 - GENERAL BINARY TREE EDITOR, TYPE DETECTION, EXTRAS
 *
 *  Nodes are addressed from Python by their PREORDER INDEX - exactly the
 *  numbering that tree_flatten() uses (root = 0). After every edit Python
 *  calls tree_flatten() again, so indexes are always fresh.
 * ===================================================================== */

/* ---------- Find a node by preorder index ---------- */
typedef struct {
    int target, count, side, depth;
    Node *found, *parent;
} Find;

static void find_rec(Node *t, Node *parent, int side, int depth, Find *f) {
    if (!t || f->found) return;
    if (f->count == f->target) {
        f->found = t; f->parent = parent; f->side = side; f->depth = depth;
        return;
    }
    f->count++;
    find_rec(t->left,  t, 0, depth + 1, f);
    find_rec(t->right, t, 1, depth + 1, f);
}

static Node *find_node(Node *root, int idx, Node **parent, int *side, int *depth) {
    Find f = { idx, 0, 0, 0, NULL, NULL };
    if (idx < 0) return NULL;
    find_rec(root, NULL, 0, 0, &f);
    if (parent) *parent = f.parent;
    if (side)   *side   = f.side;
    if (depth)  *depth  = f.depth;
    return f.found;
}

/* ---------- Editing ---------- */

/* A brand-new single-node tree. */
EXPORT Node *tree_new_root(int v) { return new_node(v); }

/* Add a child to node `idx` on side 0 (left) or 1 (right).
 * Returns 1 on success, 0 if the slot is taken / idx invalid / out of memory. */
EXPORT int tree_add_child(Node *root, int idx, int side, int v) {
    Node *t = find_node(root, idx, NULL, NULL, NULL);
    if (!t) return 0;
    Node **slot = (side == 0) ? &t->left : &t->right;
    if (*slot) return 0;
    *slot = new_node(v);
    return *slot != NULL;
}

EXPORT int tree_set_value(Node *root, int idx, int v) {
    Node *t = find_node(root, idx, NULL, NULL, NULL);
    if (!t) return 0;
    t->val = v;
    return 1;
}

/* Delete node `idx` and everything below it. Returns the (possibly NULL)
 * new root: deleting the root empties the tree. */
EXPORT Node *tree_delete_subtree(Node *root, int idx) {
    Node *parent = NULL; int side = 0;
    Node *t = find_node(root, idx, &parent, &side, NULL);
    if (!t) return root;
    if (!parent) { tree_free(t); return NULL; }
    if (side == 0) parent->left = NULL; else parent->right = NULL;
    tree_free(t);
    return root;
}

/* Depth of node `idx` (root = 0), or -1 if idx is invalid. */
EXPORT int tree_node_depth(Node *root, int idx) {
    int d = 0;
    if (!find_node(root, idx, NULL, NULL, &d)) return -1;
    return d;
}

/* Deep copy (used for undo snapshots). */
EXPORT Node *tree_clone(Node *root) {
    if (!root) return NULL;
    Node *n = new_node(root->val);
    if (!n) return NULL;
    n->left  = tree_clone(root->left);
    n->right = tree_clone(root->right);
    return n;
}

/* ---------- Level-order + traversal orders as flatten indexes ---------- */

/* Breadth-first order of node pointers into q (capacity >= tree size). */
static int level_nodes(Node *root, Node **q) {
    int head = 0, tail = 0;
    if (!root) return 0;
    q[tail++] = root;
    while (head < tail) {
        Node *t = q[head++];
        if (t->left)  q[tail++] = t->left;
        if (t->right) q[tail++] = t->right;
    }
    return tail;
}

EXPORT int tree_levelorder(Node *root, int *out) {
    int n = tree_size(root);
    if (n == 0) return 0;
    Node **q = (Node **)malloc(n * sizeof(Node *));
    if (!q) return 0;
    int m = level_nodes(root, q);
    for (int i = 0; i < m; i++) out[i] = q[i]->val;
    free(q);
    return m;
}

static void collect_pre(Node *t, Node **a, int *k) {
    if (!t) return;
    a[(*k)++] = t; collect_pre(t->left, a, k); collect_pre(t->right, a, k);
}
static void collect_in(Node *t, Node **a, int *k) {
    if (!t) return;
    collect_in(t->left, a, k); a[(*k)++] = t; collect_in(t->right, a, k);
}
static void collect_post(Node *t, Node **a, int *k) {
    if (!t) return;
    collect_post(t->left, a, k); collect_post(t->right, a, k); a[(*k)++] = t;
}

/* Visiting order as FLATTEN INDEXES (not values), so the GUI can highlight the
 * right node even when values repeat. kind: 0=pre 1=in 2=post 3=level. */
EXPORT int tree_order_idx(Node *root, int kind, int *out) {
    int n = tree_size(root);
    if (n == 0) return 0;
    Node **pre_nodes = (Node **)malloc(n * sizeof(Node *));
    Node **ord = (Node **)malloc(n * sizeof(Node *));
    if (!pre_nodes || !ord) { free(pre_nodes); free(ord); return 0; }
    int k = 0, m = 0;
    collect_pre(root, pre_nodes, &k);
    if (kind == 0)      { for (int i = 0; i < n; i++) ord[i] = pre_nodes[i]; m = n; }
    else if (kind == 1) { collect_in(root, ord, &m); }
    else if (kind == 2) { collect_post(root, ord, &m); }
    else                { m = level_nodes(root, ord); }
    for (int i = 0; i < m; i++) {
        out[i] = -1;
        for (int j = 0; j < n; j++) if (pre_nodes[j] == ord[i]) { out[i] = j; break; }
    }
    free(pre_nodes); free(ord);
    return m;
}

/* ---------- Statistics ----------
 * out[0]=nodes out[1]=height(edges, -1 if empty) out[2]=leaves
 * out[3]=internal nodes out[4]=min value out[5]=max value */
static void stats_rec(Node *t, int *leaves, int *mn, int *mx, int *first) {
    if (!t) return;
    if (!t->left && !t->right) (*leaves)++;
    if (*first) { *mn = *mx = t->val; *first = 0; }
    else { if (t->val < *mn) *mn = t->val; if (t->val > *mx) *mx = t->val; }
    stats_rec(t->left, leaves, mn, mx, first);
    stats_rec(t->right, leaves, mn, mx, first);
}

EXPORT void tree_stats(Node *root, int *out) {
    int leaves = 0, mn = 0, mx = 0, first = 1;
    stats_rec(root, &leaves, &mn, &mx, &first);
    out[0] = tree_size(root);
    out[1] = tree_height(root);
    out[2] = leaves;
    out[3] = out[0] - leaves;
    out[4] = mn;
    out[5] = mx;
}

/* ---------- Tree type detection ----------
 * Writes one line per type into buf:  name TAB (1|0) TAB reason NEWLINE
 * (reason explains WHY it is, or WHY NOT). Returns the length written. */
static void emit(char *buf, int cap, int *len, const char *name, int ok,
                 const char *fmt, ...) {
    if (*len >= cap - 1) return;
    int w = snprintf(buf + *len, cap - *len, "%s\t%d\t", name, ok);
    if (w < 0 || w >= cap - *len) return;
    *len += w;
    va_list ap;
    va_start(ap, fmt);
    w = vsnprintf(buf + *len, cap - *len, fmt, ap);
    va_end(ap);
    if (w < 0) return;
    if (w >= cap - *len) w = cap - *len - 1;
    *len += w;
    if (*len < cap - 1) { buf[(*len)++] = '\n'; buf[*len] = '\0'; }
}

/* First node (preorder) with exactly one child. */
static Node *first_one_child(Node *t) {
    if (!t) return NULL;
    if ((t->left != NULL) != (t->right != NULL)) return t;
    Node *r = first_one_child(t->left);
    return r ? r : first_one_child(t->right);
}

/* First node (preorder) with two children. */
static Node *first_two_children(Node *t) {
    if (!t) return NULL;
    if (t->left && t->right) return t;
    Node *r = first_two_children(t->left);
    return r ? r : first_two_children(t->right);
}

static void leaf_depths(Node *t, int d, int *mn, int *mx) {
    if (!t) return;
    if (!t->left && !t->right) {
        if (d < *mn) *mn = d;
        if (d > *mx) *mx = d;
        return;
    }
    leaf_depths(t->left, d + 1, mn, mx);
    leaf_depths(t->right, d + 1, mn, mx);
}

/* Returns the height, or -2 if some node is unbalanced (reported in bad/la/ra). */
static int balanced_rec(Node *t, Node **bad, int *la, int *ra) {
    if (!t) return -1;
    int l = balanced_rec(t->left, bad, la, ra);
    if (l == -2) return -2;
    int r = balanced_rec(t->right, bad, la, ra);
    if (r == -2) return -2;
    int diff = l > r ? l - r : r - l;
    if (diff > 1) { *bad = t; *la = l; *ra = r; return -2; }
    return 1 + (l > r ? l : r);
}

/* First node whose child breaks the heap rule (min-heap: child < parent). */
static Node *heap_violation(Node *t, int minheap, Node **child) {
    if (!t) return NULL;
    Node *kids[2] = { t->left, t->right };
    for (int i = 0; i < 2; i++) {
        if (!kids[i]) continue;
        int bad = minheap ? (kids[i]->val < t->val) : (kids[i]->val > t->val);
        if (bad) { *child = kids[i]; return t; }
    }
    Node *r = heap_violation(t->left, minheap, child);
    return r ? r : heap_violation(t->right, minheap, child);
}

EXPORT int tree_classify(Node *root, char *buf, int cap) {
    int len = 0;
    if (cap > 0) buf[0] = '\0';
    int n = tree_size(root);
    if (n == 0) {
        emit(buf, cap, &len, "Empty tree", 1, "there are no nodes");
        return len;
    }
    if (n == 1) emit(buf, cap, &len, "Single node", 1, "only a root, no children");

    /* Full */
    Node *one = first_one_child(root);
    int is_full = (one == NULL);
    if (is_full) emit(buf, cap, &len, "Full", 1, "every node has 0 or 2 children");
    else emit(buf, cap, &len, "Full", 0, "node %d has only one child", one->val);

    /* Perfect */
    int mn = 1 << 30, mx = -1;
    leaf_depths(root, 0, &mn, &mx);
    if (is_full && mn == mx)
        emit(buf, cap, &len, "Perfect", 1, "full, and every leaf is at depth %d", mn);
    else if (!is_full)
        emit(buf, cap, &len, "Perfect", 0, "it is not full");
    else
        emit(buf, cap, &len, "Perfect", 0, "leaves are at different depths (%d to %d)", mn, mx);

    /* Complete: BFS including empty slots; after the first gap no node may appear */
    int is_complete = 1;
    Node *gap = NULL;
    Node **q = (Node **)malloc((2 * n + 3) * sizeof(Node *));
    if (q) {
        int head = 0, tail = 0, seen_null = 0;
        q[tail++] = root;
        while (head < tail) {
            Node *t = q[head++];
            if (!t) { seen_null = 1; continue; }
            if (seen_null) { gap = t; is_complete = 0; break; }
            q[tail++] = t->left;
            q[tail++] = t->right;
        }
        free(q);
    }
    if (is_complete)
        emit(buf, cap, &len, "Complete", 1, "all levels full except maybe the last, filled left to right");
    else
        emit(buf, cap, &len, "Complete", 0, "node %d appears after a missing child in level order", gap->val);

    /* Height-balanced */
    Node *bad = NULL; int la = 0, ra = 0;
    if (balanced_rec(root, &bad, &la, &ra) != -2)
        emit(buf, cap, &len, "Height-balanced", 1, "subtree heights differ by at most 1 at every node");
    else
        emit(buf, cap, &len, "Height-balanced", 0,
             "node %d has left height %d and right height %d", bad->val, la + 1, ra + 1);

    /* Degenerate / skewed */
    Node *two = first_two_children(root);
    if (two) {
        emit(buf, cap, &len, "Degenerate (skewed)", 0, "node %d has two children", two->val);
    } else if (n == 1) {
        emit(buf, cap, &len, "Degenerate (skewed)", 1, "trivially: no node has two children");
    } else {
        Node *cur = root;
        int only_left = 0, only_right = 0;
        while (cur) {
            if (cur->left && !cur->right) { only_left++;  cur = cur->left; }
            else if (cur->right && !cur->left) { only_right++; cur = cur->right; }
            else break;
        }
        if (only_right == 0)     emit(buf, cap, &len, "Degenerate (skewed)", 1, "left-skewed: a single chain going left");
        else if (only_left == 0) emit(buf, cap, &len, "Degenerate (skewed)", 1, "right-skewed: a single chain going right");
        else                     emit(buf, cap, &len, "Degenerate (skewed)", 1, "zig-zag: a single chain switching direction");
    }

    /* BST: inorder strictly increasing */
    {
        int *io = (int *)malloc(n * sizeof(int));
        if (io) {
            tree_inorder(root, io);
            int bad_i = -1;
            for (int i = 1; i < n; i++) if (io[i] <= io[i - 1]) { bad_i = i; break; }
            if (bad_i < 0)
                emit(buf, cap, &len, "Binary Search Tree", 1, "inorder is strictly increasing");
            else if (io[bad_i] == io[bad_i - 1])
                emit(buf, cap, &len, "Binary Search Tree", 0, "value %d appears twice in a row in inorder (duplicate)", io[bad_i]);
            else
                emit(buf, cap, &len, "Binary Search Tree", 0, "inorder has %d before %d (not increasing)", io[bad_i - 1], io[bad_i]);
            free(io);
        }
    }

    /* Heaps (need a complete tree) */
    for (int pass = 0; pass < 2; pass++) {
        int minheap = (pass == 0);
        const char *name = minheap ? "Min-Heap" : "Max-Heap";
        if (!is_complete) {
            emit(buf, cap, &len, name, 0, "the tree is not complete");
        } else {
            Node *child = NULL;
            Node *p = heap_violation(root, minheap, &child);
            if (!p)
                emit(buf, cap, &len, name, 1, minheap ? "complete, and every parent <= its children"
                                                       : "complete, and every parent >= its children");
            else
                emit(buf, cap, &len, name, 0, "node %d and its child %d break the rule", p->val, child->val);
        }
    }
    return len;
}

/* ---------- Extra reconstruction: inorder + level-order ---------- */
static Node *build_il(const int *io, int lo, int hi, const int *lv, int m, int *fail) {
    if (*fail) return NULL;
    if (m == 0 && lo > hi) return NULL;
    if (m != hi - lo + 1) { *fail = 1; return NULL; }

    int v = lv[0], k = -1;
    for (int i = lo; i <= hi; i++) if (io[i] == v) { k = i; break; }
    if (k < 0) { *fail = 1; return NULL; }

    /* Split the remaining level-order values into left and right parts,
     * keeping their relative order (that is the key trick). */
    int *ll = (int *)malloc(m * sizeof(int));
    int *rl = (int *)malloc(m * sizeof(int));
    int nl = 0, nr = 0;
    if (!ll || !rl) { free(ll); free(rl); *fail = 1; return NULL; }
    for (int i = 1; i < m; i++) {
        int p = -1;
        for (int j = lo; j <= hi; j++) if (io[j] == lv[i]) { p = j; break; }
        if (p < 0 || p == k) { *fail = 1; break; }
        if (p < k) ll[nl++] = lv[i]; else rl[nr++] = lv[i];
    }
    if (!*fail && (nl != k - lo || nr != hi - k)) *fail = 1;

    Node *root = NULL;
    if (!*fail) {
        root = new_node(v);
        if (!root) *fail = 1;
    }
    if (!*fail) {
        root->left  = build_il(io, lo, k - 1, ll, nl, fail);
        root->right = build_il(io, k + 1, hi, rl, nr, fail);
    }
    free(ll); free(rl);
    if (*fail) { tree_free(root); return NULL; }
    return root;
}

EXPORT Node *tree_from_in_level(const int *io, const int *lv, int n) {
    int fail = 0;
    if (n <= 0) return NULL;
    return build_il(io, 0, n - 1, lv, n, &fail);
}

/* ---------- Build from flat arrays (used by "Load JSON") ----------
 * vals/L/R as produced by tree_flatten. Returns NULL if the arrays do not
 * describe one valid tree rooted at index 0. */
EXPORT Node *tree_from_arrays(const int *vals, const int *L, const int *R, int n) {
    if (n <= 0) return NULL;
    Node **nd = (Node **)calloc(n, sizeof(Node *));
    int *parents = (int *)calloc(n, sizeof(int));
    int ok = (nd && parents);
    for (int i = 0; ok && i < n; i++) {
        nd[i] = new_node(vals[i]);
        if (!nd[i]) ok = 0;
    }
    for (int i = 0; ok && i < n; i++) {
        int kids[2] = { L[i], R[i] };
        for (int s = 0; s < 2; s++) {
            int c = kids[s];
            if (c == -1) continue;
            if (c <= 0 || c >= n || c == i || ++parents[c] > 1) { ok = 0; break; }
            if (s == 0) nd[i]->left = nd[c]; else nd[i]->right = nd[c];
        }
    }
    Node *root = ok ? nd[0] : NULL;
    if (ok && tree_size(root) != n) ok = 0;   /* some node unreachable from the root */
    if (!ok) {
        if (nd) for (int i = 0; i < n; i++) free(nd[i]);   /* free one by one: links may be bad */
        root = NULL;
    }
    free(nd); free(parents);
    return root;
}

/* ---------- Random general binary tree ---------- */
static unsigned int rnd(unsigned int *s) {   /* xorshift32 */
    *s ^= *s << 13; *s ^= *s >> 17; *s ^= *s << 5;
    return *s;
}

/* n nodes, random shape, distinct random values. Repeatedly attaches a new node
 * to a random existing node that still has a free child slot. */
EXPORT Node *tree_random(int n, unsigned int seed) {
    if (n <= 0) return NULL;
    unsigned int s = seed ? seed : 2463534242u;
    int maxv = (3 * n > 99) ? 3 * n : 99;
    int *pool = (int *)malloc(maxv * sizeof(int));
    Node **nodes = (Node **)calloc(n, sizeof(Node *));
    int *cand = (int *)malloc(n * sizeof(int));
    Node *root = NULL;
    if (!pool || !nodes || !cand) goto done;

    for (int i = 0; i < maxv; i++) pool[i] = i + 1;
    for (int i = 0; i < n; i++) {                 /* partial Fisher-Yates shuffle */
        int j = i + (int)(rnd(&s) % (unsigned)(maxv - i));
        int tmp = pool[i]; pool[i] = pool[j]; pool[j] = tmp;
    }
    nodes[0] = new_node(pool[0]);
    if (!nodes[0]) goto done;
    for (int count = 1; count < n; count++) {
        int m = 0;
        for (int i = 0; i < count; i++)
            if (!nodes[i]->left || !nodes[i]->right) cand[m++] = i;
        Node *p = nodes[cand[rnd(&s) % (unsigned)m]];
        Node *c = new_node(pool[count]);
        if (!c) { tree_free(nodes[0]); nodes[0] = NULL; goto done; }
        nodes[count] = c;
        int left_free = (p->left == NULL), right_free = (p->right == NULL);
        int go_left = (left_free && right_free) ? (int)(rnd(&s) & 1u) : left_free;
        if (go_left) p->left = c; else p->right = c;
    }
    root = nodes[0];
done:
    free(pool); free(nodes); free(cand);
    return root;
}
