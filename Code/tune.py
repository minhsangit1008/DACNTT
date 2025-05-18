from collections import defaultdict
import time
import psutil
import os
import json
import pandas as pd
import logging

# Thiết lập logging
logging.basicConfig(level=logging.INFO, filename='howi_mto_tune.log', filemode='w',
                    format='%(asctime)s - %(levelname)s - %(message)s')

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
    try:
        with open(file_path, 'r') as f:
            for line in f:
                parts = line.strip().split(':')
                if len(parts) < 2:
                    continue
                items = parts[1].strip().split()
                valid_items = [item for item in items if item in weight_dict]
                if valid_items:
                    database.append(set(valid_items))
    except FileNotFoundError:
        logging.error(f"File '{file_path}' not found.")
        print(f"Error: File '{file_path}' not found.")
        return []
    return database

# Đọc weight_dict từ file
def load_weight_dict(file_path):
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"File '{file_path}' not found.")
        print(f"Error: File '{file_path}' not found.")
        return {}
    except json.JSONDecodeError:
        logging.error(f"File '{file_path}' contains invalid JSON.")
        print(f"Error: File '{file_path}' contains invalid JSON.")
        return {}

# Tính Transaction Occupancy (TO)
def calculate_TO(database):
    total_items = sum(len(t) for t in database)
    if total_items == 0:
        logging.error("The database is empty.")
        print("Error: The database is empty.")
        return [0] * len(database)
    return [len(t) / total_items for t in database]

# Tính Weighted Support để sắp xếp mục và cắt tỉa
def calculate_weighted_support(database, TO, weight_dict, min_ws=0.01):
    ws = defaultdict(float)
    for tid, t in enumerate(database):
        for item in t:
            ws[item] += TO[tid] * weight_dict[item]
    filtered_ws = {item: w for item, w in ws.items() if w >= min_ws}
    logging.info(f"Number of items after pruning (min_ws={min_ws}): {len(filtered_ws)}")
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
    
    logging.debug(f"Itemset: {itemset}, tids: {tids}")
    WIO = sum(TO[tid] * sum(weight_dict[item] for item in itemset) / len(itemset) for tid in tids) if tids else 0.0
    
    WIOUB_tids = set()
    for item in itemset:
        for node in fp_tree.header_table[item]:
            for path, tid_list in fp_tree.tid_map.items():
                for tid, count, nodes in tid_list:
                    if node in nodes:
                        WIOUB_tids.add(tid)
    
    logging.debug(f"Itemset: {itemset}, WIOUB_tids: {WIOUB_tids}")
    WIOUB = sum(TO[tid] * max(weight_dict[item] for item in itemset) for tid in WIOUB_tids) if WIOUB_tids else 0.0
    
    logging.debug(f"Itemset: {itemset}, WIO: {WIO:.3f}, WIOUB: {WIOUB:.3f}")
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
    
    logging.info(f"Number of items after WIOUB pruning: {len(items)}")
    
    for item, _ in items:
        new_prefix = prefix + [item]
        WIO, WIOUB, tids = calculate_WIO_WIOUB(new_prefix, fp_tree, TO, weight_dict)
        
        # Chỉ thêm nếu WIO >= MinWIO và WIOUB >= MinWIO
        if WIO >= MinWIO and WIOUB >= MinWIO:
            HOI.append((new_prefix, WIO))
            logging.info(f"Added itemset: {new_prefix}, WIO: {WIO:.3f}, WIOUB: {WIOUB:.3f}")
        else:
            logging.info(f"Skipped itemset: {new_prefix}, WIO: {WIO:.3f}, WIOUB: {WIOUB:.3f} (does not meet MinWIO)")
        
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
    
    logging.info("FP-Tree structure (first 10 nodes):")
    fp_tree.print_tree(max_nodes=10)
    
    hoimto_results = fp_growth(fp_tree, TO, weight_dict, MinWIO)
    return hoimto_results

# Đo bộ nhớ đã sửa
def get_memory_usage():
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / 1024 / 1024  # MB
    mem = max(mem, 0.0)  # Đảm bảo không âm
    logging.debug(f"Memory measured: {mem:.3f} MB")
    return mem

# Thử nghiệm tham số
def tune_parameters(transactions_file, weights_file):
    weight_dict = load_weight_dict(weights_file)
    if not weight_dict:
        logging.error("Exiting due to weight_dict load failure.")
        print("Error: Unable to load weight_dict. Exiting.")
        return
    
    database = load_weighted_database(transactions_file, weight_dict)
    if not database:
        logging.error("Exiting due to database load failure.")
        print("Error: No valid transactions loaded.")
        return
    
    # Thêm các ngưỡng mới để đạt ~50–60 itemset
    min_wio_values = [0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5]
    min_ws_values = [0.001, 0.005, 0.01, 0.05, 0.1, 0.2, 0.3]
    
    results = []
    
    for min_wio in min_wio_values:
        for min_ws in min_ws_values:
            logging.info(f"Testing MinWIO={min_wio}, min_ws={min_ws}")
            print(f"\nTesting MinWIO={min_wio}, min_ws={min_ws}")
            
            start_time = time.time()
            start_memory = get_memory_usage()
            hoimto_results = HOWI_MTO(database, min_wio, weight_dict, min_ws)
            end_time = time.time()
            end_memory = get_memory_usage()
            
            num_itemsets = len(hoimto_results)
            time_taken = end_time - start_time
            memory_used = max(end_memory - start_memory, 0.0)  # Đảm bảo không âm
            
            results.append({
                'MinWIO': min_wio,
                'min_ws': min_ws,
                'NumItemsets': num_itemsets,
                'Time(s)': time_taken,
                'Memory(MB)': memory_used
            })
            
            logging.info(f"Results: {num_itemsets} itemsets, {time_taken:.3f}s, {memory_used:.3f}MB")
            logging.debug(f"Start memory: {start_memory:.3f}MB, End memory: {end_memory:.3f}MB")
            print(f"Found {num_itemsets} itemsets")
            print(f"Time: {time_taken:.3f} seconds")
            print(f"Memory: {memory_used:.3f} MB")
            if num_itemsets > 0:
                print("Top 5 itemsets:")
                for itemset, WIO in hoimto_results[:5]:
                    print(f"Itemset: {itemset}, WIO: {WIO:.3f}")
    
    results_df = pd.DataFrame(results)
    results_df.to_csv('result.csv', index=False)
    logging.info("Results saved to results_new.csv")
    print("\nResults saved to results_new.csv")

if __name__ == "__main__":
    transactions_file = "online_retail_transactions.txt"
    weights_file = "weight_dict.txt"
    tune_parameters(transactions_file, weights_file)