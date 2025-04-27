from collections import defaultdict
import time
import psutil
import os
import json

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

# Tính WIO và WIOUB từ FP-Tree
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
    
    print(f"Debug - Itemset: {itemset}, tids: {tids}")
    WIO = sum(TO[tid] * sum(weight_dict[item] for item in itemset) / len(itemset) for tid in tids) if tids else 0.0
    
    WIOUB_tids = set()
    for item in itemset:
        for node in fp_tree.header_table[item]:
            for path, tid_list in fp_tree.tid_map.items():
                for tid, count, nodes in tid_list:
                    if node in nodes:
                        WIOUB_tids.add(tid)
    
    print(f"Debug - Itemset: {itemset}, WIOUB_tids: {WIOUB_tids}")
    WIOUB = sum(TO[tid] * max(weight_dict[item] for item in itemset) for tid in WIOUB_tids) if WIOUB_tids else 0.0
    
    print(f"Debug - Itemset: {itemset}, WIO: {WIO:.3f}, WIOUB: {WIOUB:.3f}")
    return WIO, WIOUB, tids

# Ước lượng nhanh WIOUB cho một mục đơn
def estimate_WIOUB(item, fp_tree, TO, weight_dict):
    WIOUB_tids = set()
    for node in fp_tree.header_table[item]:
        for path, tid_list in fp_tree.tid_map.items():
            for tid, count, nodes in tid_list:
                if node in nodes:
                    WIOUB_tids.add(tid)
    WIOUB = sum(TO[tid] * weight_dict[item] for tid in WIOUB_tids) if WIOUB_tids else 0.0
    return WIOUB

# Khai thác tập mục kiểu FP-Growth với cắt tỉa mạnh hơn
def fp_growth(fp_tree, TO, weight_dict, MinWIO, prefix=None, HOI=None):
    if HOI is None:
        HOI = []
    if prefix is None:
        prefix = []
    
    # Lọc các mục có WIOUB >= MinWIO trước khi xử lý
    items = []
    for item in fp_tree.header_table.keys():
        WIOUB = estimate_WIOUB(item, fp_tree, TO, weight_dict)
        if WIOUB >= MinWIO:
            items.append((item, WIOUB))
    
    items = sorted(items, key=lambda x: fp_tree.item_counts[x[0]])
    
    print(f"Debug - Number of items after WIOUB pruning: {len(items)}")
    
    for item, _ in items:
        new_prefix = prefix + [item]
        WIO, WIOUB, tids = calculate_WIO_WIOUB(new_prefix, fp_tree, TO, weight_dict)
        
        # Chỉ thêm nếu WIO >= MinWIO và WIOUB >= MinWIO
        if WIO >= MinWIO and WIOUB >= MinWIO:
            HOI.append((new_prefix, WIO))
            print(f"Added itemset: {new_prefix}, WIO: {WIO:.3f}, WIOUB: {WIOUB:.3f}")
        else:
            print(f"Skipped itemset: {new_prefix}, WIO: {WIO:.3f}, WIOUB: {WIOUB:.3f} (does not meet MinWIO)")
        
        # Chỉ tiếp tục mở rộng nếu WIOUB >= MinWIO
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
            
            # Kiểm tra lại cây con trước khi đệ quy
            if cond_tree.header_table:
                fp_growth(cond_tree, TO, weight_dict, MinWIO, new_prefix, HOI)
    
    return HOI

# Thuật toán HOWI-MTO với FP-Tree
def HOWI_MTO(database, MinWIO, weight_dict, min_ws=0.01):
    TO = calculate_TO(database)
    fp_tree, ws = build_fp_tree(database, TO, weight_dict, min_ws)
    
    print("FP-Tree structure (first 10 nodes):")
    fp_tree.print_tree(max_nodes=10)
    
    hoimto_results = fp_growth(fp_tree, TO, weight_dict, MinWIO)
    return hoimto_results

# Đo bộ nhớ
def get_memory_usage():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

# Chạy thử
if __name__ == "__main__":
    transactions_file = "online_retail_transactions.txt"
    weights_file = "weight_dict.txt"
    
    weight_dict = load_weight_dict(weights_file)
    database = load_weighted_database(transactions_file, weight_dict)
    MinWIO = 0.05
    min_ws = 0.01
    
    print("HOWI-MTO results (with FP-Tree):")
    start_time = time.time()
    start_memory = get_memory_usage()
    hoimto_results = HOWI_MTO(database, MinWIO, weight_dict, min_ws)
    end_time = time.time()
    end_memory = get_memory_usage()
    
    print(f"Found {len(hoimto_results)} itemsets")
    for itemset, WIO in hoimto_results[:10]:
        print(f"Itemset: {itemset}, WIO: {WIO:.3f}")
    print(f"Time: {end_time - start_time:.3f} seconds")
    print(f"Memory: {end_memory - start_memory:.3f} MB")