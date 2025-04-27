from collections import defaultdict
import time
import psutil
import os
import json
import matplotlib.pyplot as plt

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

    def add_transaction(self, transaction, count, tid):
        current = self.root
        path = []
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
        self.tid_map[tuple(path)].append((tid, count))

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

# Tính WIO và WIOUB từ FP-Tree (sửa để chính xác hơn)
def calculate_WIO_WIOUB_fp(itemset, fp_tree, TO, weight_dict):
    tids = None
    itemset = sorted(itemset, key=lambda x: fp_tree.item_counts[x], reverse=True)
    for item in itemset:
        item_tids = set()
        for node in fp_tree.header_table[item]:
            path_tids = set()
            current = node
            while current.parent is not None:
                path = tuple(path for path, tid_list in fp_tree.tid_map.items() if current in tid_list)
                for p in path:
                    for tid, _ in fp_tree.tid_map[p]:
                        path_tids.add(tid)
                current = current.parent
            item_tids.update(path_tids)
        if tids is None:
            tids = item_tids
        else:
            tids &= item_tids
    
    # Sửa cách tính WIO: Nhân với count từ tid_map
    WIO = 0
    for path, tid_list in fp_tree.tid_map.items():
        if all(item in path for item in itemset):
            for tid, count in tid_list:
                if tid in tids:
                    WIO += count * sum(weight_dict[item] for item in itemset) / len(itemset)
    
    WIOUB_tids = set()
    for item in itemset:
        for node in fp_tree.header_table[item]:
            path_tids = set()
            current = node
            while current.parent is not None:
                path = tuple(path for path, tid_list in fp_tree.tid_map.items() if current in tid_list)
                for p in path:
                    for tid, _ in fp_tree.tid_map[p]:
                        path_tids.add(tid)
                current = current.parent
            WIOUB_tids.update(path_tids)
    
    WIOUB = sum(TO[tid] * max(weight_dict[item] for item in itemset) for tid in WIOUB_tids)
    return WIO, WIOUB, tids

# Khai thác tập mục kiểu FP-Growth
def fp_growth(fp_tree, TO, weight_dict, MinWIO, prefix=None, HOI=None):
    if HOI is None:
        HOI = []
    if prefix is None:
        prefix = []
    
    items = sorted(fp_tree.header_table.keys(), key=lambda x: fp_tree.item_counts[x])
    
    for item in items:
        new_prefix = prefix + [item]
        WIO, WIOUB, tids = calculate_WIO_WIOUB_fp(new_prefix, fp_tree, TO, weight_dict)
        
        if WIOUB >= MinWIO:
            if WIO >= MinWIO:
                HOI.append((new_prefix, WIO))
            
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
            
            fp_growth(cond_tree, TO, weight_dict, MinWIO, new_prefix, HOI)
    
    return HOI

# --- Phiên bản tuần 35 (HOWI-MTO không dùng FP-Tree) ---

# Tính WIO và WIOUB (phiên bản tuần 35, sửa để chính xác hơn)
def calculate_WIO_WIOUB_no_fp(itemset, database, TO, weight_dict):
    tids = [tid for tid, t in enumerate(database) if set(itemset).issubset(t)]
    WIO = sum(TO[tid] * sum(weight_dict[item] for item in itemset) / len(itemset) for tid in tids)
    WIOUB = sum(TO[tid] * max(weight_dict[item] for item in itemset if item in t)
                for tid, t in enumerate(database) if any(item in t for item in itemset))
    return WIO, WIOUB, tids

# Thuật toán HOWI-MTO không dùng FP-Tree (tuần 35)
def HOWI_MTO_no_fp(database, MinWIO, weight_dict):
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

# Đọc weight_dict từ file
def load_weight_dict(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

# Tính Transaction Occupancy (TO)
def calculate_TO(database):
    total_items = sum(len(t) for t in database)
    if total_items == 0:
        return [0] * len(database)
    return [len(t) / total_items for t in database]

# Tính Weighted Support để sắp xếp mục và cắt tỉa
def calculate_weighted_support(database, TO, weight_dict, min_ws=0.01):
    ws = defaultdict(float)
    for tid, t in enumerate(database):
        for item in t:
            ws[item] += TO[tid] * weight_dict[item]
    filtered_ws = {item: w for item, w in ws.items() if w >= min_ws}
    print(f"Number of items after pruning (min_ws={min_ws}): {len(filtered_ws)}")
    return filtered_ws

# Xây dựng FP-Tree với cắt tỉa
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

# Đo bộ nhớ
def get_memory_usage():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

# Thuật toán HOWI-MTO với FP-Tree (tuần 37)
def HOWI_MTO_fp(database, MinWIO, weight_dict, min_ws=0.01):
    TO = calculate_TO(database)
    fp_tree, ws = build_fp_tree(database, TO, weight_dict, min_ws)
    
    print("FP-Tree structure (first 10 nodes):")
    fp_tree.print_tree(max_nodes=10)
    
    hoimto_results = fp_growth(fp_tree, TO, weight_dict, MinWIO)
    return hoimto_results

# Chạy và so sánh
if __name__ == "__main__":
    transactions_file = "online_retail_transactions.txt"
    weights_file = "weight_dict.txt"
    
    # Đọc weight_dict
    weight_dict = load_weight_dict(weights_file)
    
    # Đọc dữ liệu đã xử lý
    database = load_weighted_database(transactions_file, weight_dict)
    MinWIO = 0.1
    min_ws = 0.05
    
    # Chạy phiên bản tuần 37 (FP-Tree)
    print("Running HOWI-MTO with FP-Tree (Week 37):")
    start_time_fp = time.time()
    start_memory_fp = get_memory_usage()
    hoimto_results_fp = HOWI_MTO_fp(database, MinWIO, weight_dict, min_ws)
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
    hoimto_results_no_fp = HOWI_MTO_no_fp(database, MinWIO, weight_dict)
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
    
    # Biểu đồ thời gian
    plt.figure(figsize=(10, 4))
    plt.subplot(1, 3, 1)
    plt.bar(labels, times, color=['blue', 'orange'])
    plt.title('Time Comparison (seconds)')
    plt.ylabel('Time (s)')
    
    # Biểu đồ bộ nhớ
    plt.subplot(1, 3, 2)
    plt.bar(labels, memories, color=['blue', 'orange'])
    plt.title('Memory Comparison (MB)')
    plt.ylabel('Memory (MB)')
    
    # Biểu đồ số tập mục
    plt.subplot(1, 3, 3)
    plt.bar(labels, itemsets, color=['blue', 'orange'])
    plt.title('Number of Itemsets')
    plt.ylabel('Itemsets')
    
    plt.tight_layout()
    plt.savefig('comparison_chart.png')