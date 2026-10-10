/*
 * bst_engine.c - Binary tree engine (called from Python via ctypes)
 *
 * Build (Windows, MinGW-w64 gcc):  gcc -shared -O2 -o bst_engine.dll bst_engine.c
 * Build (Linux):                   gcc -shared -fPIC -O2 -o bst_engine.so bst_engine.c
 * Build (macOS):                   gcc -shared -fPIC -O2 -o bst_engine.dylib bst_engine.c
 */
#include <stdlib.h>

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
