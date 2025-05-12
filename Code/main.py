import json
import time

from collections import defaultdict

class FPNode:
    def __init__(self, item, count, parent):
        self.item = item
        self.count = count
        self.parent = parent
        self.children = {}
        self.node_link = None

class FPTree:
    def __init__(self):
        self.root = FPNode(None, 0, None)
        self.header_table = defaultdict(list)
        self.item_counts = defaultdict(float)
        self.tid_map = defaultdict(list)

    def add_transaction(self, transaction, count, tid):
        current = self.root
        path = []
        nodes_in_path = []
        for item in transaction:
            self.item_counts[item] += count
            if item in current.children:
                current.children[item].count += count
            else:
                new_node = FPNode(item, count, current)
                current.children[item] = new_node
                self.header_table[item].append(new_node)
            current = current.children[item]
            path.append(item)
            nodes_in_path.append(current)
        self.tid_map[tuple(path)].append((tid, count, nodes_in_path))

def calculate_TO(database):
    total_items = sum(len(t) for t in database)
    return [len(t) / total_items for t in database]

def calculate_weighted_support(database, TO, weight_dict, min_ws=0.01):
    ws = defaultdict(float)
    for tid, t in enumerate(database):
        for item in t:
            ws[item] += TO[tid] * weight_dict[item]
    return {item: w for item, w in ws.items() if w >= min_ws}

def build_fp_tree(database, TO, weight_dict, min_ws=0.01):
    ws = calculate_weighted_support(database, TO, weight_dict, min_ws)
    tree = FPTree()
    for tid, t in enumerate(database):
        valid_items = [item for item in t if item in ws]
        if not valid_items:
            continue
        sorted_items = sorted(valid_items, key=lambda x: ws[x], reverse=True)
        tree.add_transaction(sorted_items, TO[tid], tid)
    return tree, ws

def calculate_WIO_WIOUB(itemset, fp_tree, TO, weight_dict):
    tids = None
    itemset = sorted(itemset, key=lambda x: fp_tree.item_counts[x], reverse=True)
    for item in itemset:
        item_tids = set()
        for node in fp_tree.header_table[item]:
            for path, tid_list in fp_tree.tid_map.items():
                for tid, count, nodes in tid_list:
                    if any(n.item == node.item for n in nodes):  # FIXED
                        item_tids.add(tid)
        if tids is None:
            tids = item_tids
        else:
            tids &= item_tids

    WIO = sum(TO[tid] * sum(weight_dict[i] for i in itemset) / len(itemset) for tid in tids) if tids else 0.0

    WIOUB_tids = set()
    for item in itemset:
        for node in fp_tree.header_table[item]:
            for path, tid_list in fp_tree.tid_map.items():
                for tid, count, nodes in tid_list:
                    if any(n.item == node.item for n in nodes):  # FIXED
                        WIOUB_tids.add(tid)

    WIOUB = sum(TO[tid] * max(weight_dict[i] for i in itemset) for tid in WIOUB_tids) if WIOUB_tids else 0.0

    return WIO, WIOUB, tids

def estimate_WIOUB(item, fp_tree, TO, weight_dict):
    WIOUB_tids = set()
    for node in fp_tree.header_table[item]:
        for path, tid_list in fp_tree.tid_map.items():
            for tid, count, nodes in tid_list:
                if any(n.item == node.item for n in nodes):  # FIXED
                    WIOUB_tids.add(tid)
    return sum(TO[tid] * weight_dict[item] for tid in WIOUB_tids) if WIOUB_tids else 0.0

def fp_growth(fp_tree, TO, weight_dict, MinWIO, prefix=None, HOI=None):
    if HOI is None:
        HOI = []
    if prefix is None:
        prefix = []

    items = []
    for item in fp_tree.header_table:
        WIOUB = estimate_WIOUB(item, fp_tree, TO, weight_dict)
        if WIOUB >= MinWIO:
            items.append((item, WIOUB))

    items.sort(key=lambda x: fp_tree.item_counts[x[0]])

    for item, _ in items:
        new_prefix = prefix + [item]
        WIO, WIOUB, tids = calculate_WIO_WIOUB(new_prefix, fp_tree, TO, weight_dict)
        if WIO >= MinWIO and WIOUB >= MinWIO:
            HOI.append((new_prefix, WIO))

        if WIOUB >= MinWIO:
            cond_pattern_base = []
            for node in fp_tree.header_table[item]:
                path = []
                current = node
                while current.parent and current.parent.item is not None:
                    path.append(current.parent.item)
                    current = current.parent
                if path:
                    cond_pattern_base.append((path, node.count))

            cond_tree = FPTree()
            for path, count in cond_pattern_base:
                sorted_path = sorted(path, key=lambda x: fp_tree.item_counts[x], reverse=True)
                cond_tree.add_transaction(sorted_path, count, -1)

            if cond_tree.header_table:
                fp_growth(cond_tree, TO, weight_dict, MinWIO, new_prefix, HOI)

    return HOI

def HOWI_MTO(database, MinWIO, weight_dict, min_ws=0.01):
    TO = calculate_TO(database)
    fp_tree, ws = build_fp_tree(database, TO, weight_dict, min_ws)
    return fp_growth(fp_tree, TO, weight_dict, MinWIO)


def load_weight_dict(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

def load_weighted_database(file_path, weight_dict):
    database = []
    with open(file_path, 'r') as f:
        for line in f:
            parts = line.strip().split(':')
            if len(parts) < 2:
                continue
            items = parts[1].strip().split()
            valid_items = [item for item in items if item in weight_dict]
            if valid_items:
                database.append(set(valid_items))
    return database

if __name__ == "__main__":
    transaction_file = "online_retail_transactions.txt"
    weight_file = "weight_dict.txt"
    MinWIO = 0.05  # Ngưỡng tối thiểu WIO
    min_ws = 0.01  # Ngưỡng cắt tỉa theo Weighted Support

    print("Loading data...")
    weight_dict = load_weight_dict(weight_file)
    database = load_weighted_database(transaction_file, weight_dict)

    print("Running HOWI-MTO...")
    start = time.time()
    results = HOWI_MTO(database, MinWIO, weight_dict, min_ws)
    end = time.time()

    print(f"\nTotal itemsets found: {len(results)}")
    print(f"Execution time: {end - start:.3f} seconds\n")

    # In 10 itemsets đầu tiên (nếu có)
    for itemset, wio in results[:10]:
        print(f"Itemset: {itemset}, WIO: {wio:.4f}")
