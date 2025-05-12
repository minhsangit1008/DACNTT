import time
import psutil
import os
from collections import defaultdict
import json

# Hàm từ HOIMTO.py
def load_database(file_path):
    database = []
    with open(file_path, 'r') as f:
        for line in f:
            items = line.strip().split()[1:]  # Bỏ T1, T2,...
            database.append(set(items))
    return database

def calculate_TO(database):
    total_items = sum(len(t) for t in database)
    return [len(t) / total_items for t in database]

def calculate_IO_IOUB(itemset, database, TO):
    tids = [tid for tid, t in enumerate(database) if set(itemset).issubset(t)]
    IO = sum(TO[tid] for tid in tids)
    IOUB = sum(TO[tid] for tid, t in enumerate(database) if any(item in t for item in itemset))
    return IO, IOUB, tids

def HOIMTO(database, MinIO):
    TO = calculate_TO(database)
    HOI = []
    item_support = defaultdict(list)
    for tid, t in enumerate(database):
        for item in t:
            item_support[item].append(tid)
    
    candidates = [[item] for item in item_support]
    k = 1
    while candidates:
        next_candidates = []
        for itemset in candidates:
            IO, IOUB, tids = calculate_IO_IOUB(itemset, database, TO)
            if IOUB >= MinIO:
                if IO >= MinIO:
                    HOI.append((itemset, IO))
                    if k == 1:
                        next_candidates.extend([[itemset[0], new_item] for new_item in item_support if new_item > itemset[0]])
                    else:
                        for other in candidates:
                            if other[:k-1] == itemset[:k-1] and other[k-1] > itemset[k-1]:
                                next_candidates.append(itemset + [other[k-1]])
        candidates = next_candidates
        k += 1
    
    return HOI

# Hàm từ HOIW-MTOwithFPTreeUpdate.py
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

def load_weighted_database(file_path, weight_dict):
    database = []
    with open(file_path, 'r') as f:
        for line in f:
            parts = line.strip().split(':')
            if len(parts) < 2:
                continue
            items = parts[1].strip().split()
            valid_items = [item for item in items if item in weight_dict]
            if not valid_items:
                continue
            database.append(set(valid_items))
    return database

def load_weight_dict(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

def calculate_weighted_support(database, TO, weight_dict, min_ws=0.01):
    ws = defaultdict(float)
    for tid, t in enumerate(database):
        for item in t:
            ws[item] += TO[tid] * weight_dict[item]
    filtered_ws = {item: w for item, w in ws.items() if w >= min_ws}
    return filtered_ws

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
                    if node in nodes:
                        item_tids.add(tid)
        if tids is None:
            tids = item_tids
        else:
            tids &= item_tids
    
    WIO = sum(TO[tid] * sum(weight_dict[item] for item in itemset) / len(itemset) for tid in tids) if tids else 0.0
    
    WIOUB_tids = set()
    for item in itemset:
        for node in fp_tree.header_table[item]:
            for path, tid_list in fp_tree.tid_map.items():
                for tid, count, nodes in tid_list:
                    if node in nodes:
                        WIOUB_tids.add(tid)
    
    WIOUB = sum(TO[tid] * max(weight_dict[item] for item in itemset) for tid in WIOUB_tids) if WIOUB_tids else 0.0
    
    return WIO, WIOUB, tids

def estimate_WIOUB(item, fp_tree, TO, weight_dict):
    WIOUB_tids = set()
    for node in fp_tree.header_table[item]:
        for path, tid_list in fp_tree.tid_map.items():
            for tid, count, nodes in tid_list:
                if node in nodes:
                    WIOUB_tids.add(tid)
    WIOUB = sum(TO[tid] * weight_dict[item] for tid in WIOUB_tids) if WIOUB_tids else 0.0
    return WIOUB

def fp_growth(fp_tree, TO, weight_dict, MinWIO, prefix=None, HOI=None):
    if HOI is None:
        HOI = []
    if prefix is None:
        prefix = []
    
    items = []
    for item in fp_tree.header_table.keys():
        WIOUB = estimate_WIOUB(item, fp_tree, TO, weight_dict)
        if WIOUB >= MinWIO:
            items.append((item, WIOUB))
    
    items = sorted(items, key=lambda x: fp_tree.item_counts[x[0]])
    
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
                while current.parent is not None and current.parent.item is not None:
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
    hoimto_results = fp_growth(fp_tree, TO, weight_dict, MinWIO)
    return hoimto_results

# Hàm đo bộ nhớ
def get_memory_usage():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024  # MB

# Hàm so sánh hiệu suất
def compare_algorithms(transactions_file, weights_file, MinIO=0.3, MinWIO=0.05, min_ws=0.01):
    # Load dữ liệu
    weight_dict = load_weight_dict(weights_file)
    database_hoimto = load_database(transactions_file)
    database_howi = load_weighted_database(transactions_file, weight_dict)
    
    # Chạy HOIMTO
    print("Running HOIMTO...")
    start_time_hoimto = time.time()
    start_memory_hoimto = get_memory_usage()
    hoimto_results = HOIMTO(database_hoimto, MinIO)
    end_time_hoimto = time.time()
    end_memory_hoimto = get_memory_usage()
    
    time_hoimto = end_time_hoimto - start_time_hoimto
    memory_hoimto = end_memory_hoimto - start_memory_hoimto
    itemsets_hoimto = len(hoimto_results)
    
    # Chạy HOWI-MTO
    print("Running HOWI-MTO...")
    start_time_howi = time.time()
    start_memory_howi = get_memory_usage()
    howi_results = HOWI_MTO(database_howi, MinWIO, weight_dict, min_ws)
    end_time_howi = time.time()
    end_memory_howi = get_memory_usage()
    
    time_howi = end_time_howi - start_time_howi
    memory_howi = end_memory_howi - start_memory_howi
    itemsets_howi = len(howi_results)
    
    # In kết quả so sánh
    print("\n=== Performance Comparison ===")
    print(f"{'Metric':<20} {'HOIMTO':<15} {'HOWI-MTO':<15}")
    print("-" * 50)
    print(f"{'Time (seconds)':<20} {time_hoimto:.3f} {'':<5} {time_howi:.3f}")
    print(f"{'Memory (MB)':<20} {memory_hoimto:.3f} {'':<5} {memory_howi:.3f}")
    print(f"{'Number of Itemsets':<20} {itemsets_hoimto:<15} {itemsets_howi:<15}")

if __name__ == "__main__":
    transactions_file = "online_retail_transactions.txt"
    weights_file = "weight_dict.txt"
    compare_algorithms(transactions_file, weights_file)