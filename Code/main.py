from collections import defaultdict
import time
import psutil
import os
import json
import matplotlib.pyplot as plt
import random

# --- Phiên bản tuần 37 (HOWI-MTO với FP-Tree) ---

# Lớp nút trong FP-Tree
class FPNode:
    def __init__(self, item, count, parent):
        self.item = item
        self.count = count
        self.parent = parent
        self.children = {}
        self.node_link = None

# Lớp FP-Tree
class FPTree:
    def __init__(self):
        self.root = FPNode(None, 0, None)
        self.header_table = defaultdict(list)
        self.item_counts = defaultdict(float)
        self.tid_map = defaultdict(list)

    def add_transaction(self, transaction, count, tid, max_items_per_transaction=50):
        current = self.root
        path = []
        nodes_in_path = []
        transaction = transaction[:max_items_per_transaction]
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

    def print_tree(self, node=None, level=0, max_nodes=10):
        if max_nodes <= 0:
            return max_nodes
        if node is None:
            node = self.root
        if node.item is not None:
            print("  " * level + f"{node.item}: {node.count:.3f}")
            max_nodes -= 1
        for child in node.children.values():
            if max_nodes <= 0:
                break
            max_nodes = self.print_tree(child, level + 1, max_nodes)
        return max_nodes

# Tính WIO và WIOUB từ FP-Tree
def calculate_WIO_WIOUB_fp(itemset, fp_tree, TO, weight_dict):
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
    
    avg_weight = sum(weight_dict[item] for item in itemset) / len(itemset)
    WIO = sum(TO[tid] * avg_weight for tid in tids) if tids else 0.0
    
    WIOUB_tids = set()
    for item in itemset:
        for node in fp_tree.header_table[item]:
            for path, tid_list in fp_tree.tid_map.items():
                for tid, count, nodes in tid_list:
                    if node in nodes:
                        WIOUB_tids.add(tid)
    
    WIOUB = sum(TO[tid] * max(weight_dict[item] for item in itemset) for tid in WIOUB_tids) if WIOUB_tids else 0.0
    return WIO, WIOUB, tids

# Ước lượng WIOUB để cắt tỉa sớm
def estimate_WIOUB(item, fp_tree, TO, weight_dict):
    WIOUB_tids = set()
    for node in fp_tree.header_table[item]:
        for path, tid_list in fp_tree.tid_map.items():
            for tid, count, nodes in tid_list:
                if node in nodes:
                    WIOUB_tids.add(tid)
    WIOUB = sum(TO[tid] * weight_dict[item] for tid in WIOUB_tids) if WIOUB_tids else 0.0
    return WIOUB

# Khai thác tập mục kiểu FP-Growth với tối ưu
def fp_growth(fp_tree, TO, weight_dict, MinWIO, prefix=None, HOI=None, max_length=3):
    if HOI is None:
        HOI = []
    if prefix is None:
        prefix = []
    if len(prefix) >= max_length:
        return HOI
    
    items = []
    for item in fp_tree.header_table.keys():
        WIOUB = estimate_WIOUB(item, fp_tree, TO, weight_dict)
        if WIOUB >= MinWIO:
            items.append((item, WIOUB))
    
    items = sorted(items, key=lambda x: fp_tree.item_counts[x[0]])
    
    for item, _ in items:
        new_prefix = prefix + [item]
        WIO, WIOUB, tids = calculate_WIO_WIOUB_fp(new_prefix, fp_tree, TO, weight_dict)
        
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
                fp_growth(cond_tree, TO, weight_dict, MinWIO, new_prefix, HOI, max_length)
    
    return HOI

# --- Phiên bản tuần 35 (HOWI-MTO không dùng FP-Tree) ---

# Tính WIO và WIOUB
def calculate_WIO_WIOUB_no_fp(itemset, database, TO, weight_dict):
    tids = [tid for tid, t in enumerate(database) if set(itemset).issubset(set(t))]
    avg_weight = sum(weight_dict[item] for item in itemset) / len(itemset)
    WIO = sum(TO[tid] * avg_weight for tid in tids) if tids else 0.0
    WIOUB = sum(TO[tid] * max(weight_dict[item] for item in itemset if item in t)
                for tid, t in enumerate(database) if any(item in t for item in itemset))
    return WIO, WIOUB, tids

# Thuật toán HOWI-MTO không dùng FP-Tree (tuần 35) - Tối ưu với cắt tỉa
def HOWI_MTO_no_fp(database, MinWIO, weight_dict, min_ws=0.01, min_freq=0.01, max_length=3):
    TO = calculate_TO(database)
    
    # Cắt tỉa sớm các mục có Weighted Support nhỏ
    ws = defaultdict(float)
    freq = defaultdict(int)
    num_transactions = len(database)
    for tid, t in enumerate(database):
        for item in set(t):
            ws[item] += TO[tid] * weight_dict[item]
            freq[item] += 1
    min_freq_count = num_transactions * min_freq
    filtered_items = {item for item, w in ws.items() if w >= min_ws and freq[item] >= min_freq_count}
    print(f"Number of items after pruning (min_ws={min_ws}, min_freq={min_freq}): {len(filtered_items)}")
    
    HOI = []
    item_support = defaultdict(list)
    for tid, t in enumerate(database):
        for item in t:
            if item in filtered_items:
                item_support[item].append(tid)
    
    candidates = [[item] for item in item_support]
    k = 1
    while candidates and k <= max_length:
        next_candidates = []
        for itemset in candidates:
            WIO, WIOUB, tids = calculate_WIO_WIOUB_no_fp(itemset, database, TO, weight_dict)
            if WIOUB >= MinWIO:
                if WIO >= MinWIO:
                    HOI.append((itemset, WIO))
                    if k == 1:
                        next_candidates.extend([[itemset[0], new_item] for new_item in item_support if new_item > itemset[0]])
                    else:
                        for other in candidates:
                            if other[:k-1] == itemset[:k-1] and other[k-1] > itemset[k-1]:
                                next_candidates.append(itemset + [other[k-1]])
        candidates = next_candidates
        k += 1
    
    return HOI

# --- Hàm chung ---

# Đọc cơ sở dữ liệu và trọng số
def load_weighted_database(file_path, weight_dict, max_transactions=10000):
    database = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                parts = line.strip().split(':')
                if len(parts) < 2:
                    continue
                items = parts[1].strip().split()
                valid_items = [item for item in items if item in weight_dict]
                if not valid_items:
                    continue
                database.append(valid_items)
                if len(database) >= max_transactions:
                    break
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return []
    if not database:
        print("Error: The database is empty.")
        return []
    return database

# Đọc weight_dict từ file
def load_weight_dict(file_path):
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: File '{file_path}' is not a valid JSON.")
        return {}

# Tính Transaction Occupancy (TO)
def calculate_TO(database):
    total_items = sum(len(t) for t in database)
    if total_items == 0:
        return [0] * len(database)
    return [len(t) / total_items for t in database]

# Tính Weighted Support để sắp xếp mục và cắt tỉa
def calculate_weighted_support(database, TO, weight_dict, min_ws=0.01, min_freq=0.01):
    ws = defaultdict(float)
    freq = defaultdict(int)
    num_transactions = len(database)
    for tid, t in enumerate(database):
        for item in set(t):
            ws[item] += TO[tid] * weight_dict[item]
            freq[item] += 1
    min_freq_count = num_transactions * min_freq
    filtered_ws = {item: w for item, w in ws.items() if w >= min_ws and freq[item] >= min_freq_count}
    print(f"Number of items after pruning (min_ws={min_ws}, min_freq={min_freq}): {len(filtered_ws)}")
    return filtered_ws

# Xây dựng FP-Tree với cắt tỉa
def build_fp_tree(database, TO, weight_dict, min_ws=0.01, min_freq=0.01, max_items_per_transaction=50):
    ws = calculate_weighted_support(database, TO, weight_dict, min_ws, min_freq)
    tree = FPTree()
    for tid, t in enumerate(database):
        valid_items = [item for item in t if item in ws]
        if not valid_items:
            continue
        sorted_items = sorted(valid_items, key=lambda x: ws[x], reverse=True)
        tree.add_transaction(sorted_items, TO[tid], tid, max_items_per_transaction)
    return tree, ws

# Đo bộ nhớ
def get_memory_usage():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

# Thuật toán HOWI-MTO với FP-Tree (tuần 37)
def HOWI_MTO_fp(database, MinWIO, weight_dict, min_ws=0.01, min_freq=0.01, max_length=3, max_items_per_transaction=50):
    TO = calculate_TO(database)
    fp_tree, ws = build_fp_tree(database, TO, weight_dict, min_ws, min_freq, max_items_per_transaction)
    
    print("FP-Tree structure (first 10 nodes):")
    fp_tree.print_tree(max_nodes=10)
    
    hoimto_results = fp_growth(fp_tree, TO, weight_dict, MinWIO, max_length=max_length)
    return hoimto_results

# Chạy và so sánh
if __name__ == "__main__":
    transactions_file = "online_retail_transactions.txt"
    weights_file = "weight_dict.txt"
    
    weight_dict = load_weight_dict(weights_file)
    if not weight_dict:
        exit()
    
    max_transactions = 100  # Giữ nguyên số lượng giao dịch
    database = load_weighted_database(transactions_file, weight_dict, max_transactions)
    if not database:
        exit()
    print(f"Loaded {len(database)} transactions")
    
    MinWIO = 0.3
    min_ws = 0.01
    min_freq = 0.01
    max_length = 3
    max_items_per_transaction = 50
    
    # Chạy phiên bản tuần 37 (FP-Tree)
    print("Running HOWI-MTO with FP-Tree (Week 37):")
    start_time_fp = time.time()
    start_memory_fp = get_memory_usage()
    hoimto_results_fp = HOWI_MTO_fp(database, MinWIO, weight_dict, min_ws, min_freq, max_length, max_items_per_transaction)
    end_time_fp = time.time()
    end_memory_fp = get_memory_usage()
    
    time_fp = end_time_fp - start_time_fp
    memory_fp = end_memory_fp - start_memory_fp
    itemsets_fp = len(hoimto_results_fp)
    
    print(f"Found {itemsets_fp} itemsets")
    for itemset, WIO in hoimto_results_fp[:10]:
        print(f"Itemset: {itemset}, WIO: {WIO:.3f}")
    print(f"Time: {time_fp:.3f} seconds")
    print(f"Memory: {memory_fp:.3f} MB")
    
    # Chạy phiên bản tuần 35 (không dùng FP-Tree)
    print("\nRunning HOWI-MTO without FP-Tree (Week 35):")
    start_time_no_fp = time.time()
    start_memory_no_fp = get_memory_usage()
    hoimto_results_no_fp = HOWI_MTO_no_fp(database, MinWIO, weight_dict, min_ws, min_freq, max_length)
    end_time_no_fp = time.time()
    end_memory_no_fp = get_memory_usage()
    
    time_no_fp = end_time_no_fp - start_time_no_fp
    memory_no_fp = end_memory_no_fp - start_memory_no_fp
    itemsets_no_fp = len(hoimto_results_no_fp)
    
    print(f"Found {itemsets_no_fp} itemsets")
    for itemset, WIO in hoimto_results_no_fp[:10]:
        print(f"Itemset: {itemset}, WIO: {WIO:.3f}")
    print(f"Time: {time_no_fp:.3f} seconds")
    print(f"Memory: {memory_no_fp:.3f} MB")
    
    # Vẽ biểu đồ so sánh
    labels = ['HOWI-MTO (FP-Tree)', 'HOWI-MTO (No FP-Tree)']
    times = [time_fp, time_no_fp]
    memories = [memory_fp, memory_no_fp]
    itemsets = [itemsets_fp, itemsets_no_fp]
    
    plt.figure(figsize=(10, 4))
    plt.subplot(1, 3, 1)
    plt.bar(labels, times, color=['blue', 'orange'])
    plt.title('Time Comparison (seconds)')
    plt.ylabel('Time (s)')
    
    plt.subplot(1, 3, 2)
    plt.bar(labels, memories, color=['blue', 'orange'])
    plt.title('Memory Comparison (MB)')
    plt.ylabel('Memory (MB)')
    
    plt.subplot(1, 3, 3)
    plt.bar(labels, itemsets, color=['blue', 'orange'])
    plt.title('Number of Itemsets')
    plt.ylabel('Itemsets')
    
    plt.tight_layout()
    plt.savefig('comparison_chart.png')