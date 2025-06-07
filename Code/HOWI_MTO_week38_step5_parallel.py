from collections import defaultdict
import time
import psutil
import os
import json
import pandas as pd
import logging
from multiprocessing import Pool, cpu_count

# Thiết lập logging
logging.basicConfig(level=logging.INFO, filename='howi_mto_week38_step5_parallel.log', filemode='w',
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Lớp nút trong FP-Tree
class FPNode:
    def __init__(self, item, count, parent):
        self.item = item
        self.count = count
        self.parent = parent
        self.children = {}
        self.node_link = None
        self.tids = set()

# Lớp FP-Tree
class FPTree:
    def __init__(self):
        self.root = FPNode(None, 0, None)
        self.header_table = defaultdict(list)
        self.item_counts = defaultdict(float)

    def add_transaction(self, transaction, count, tid):
        current = self.root
        for item in transaction:
            self.item_counts[item] += count
            if item in current.children:
                current.children[item].count += count
            else:
                new_node = FPNode(item, count, current)
                current.children[item] = new_node
                self.header_table[item].append(new_node)
            current = current.children[item]
            current.tids.add(tid)

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

# Tính Weighted Transaction Occupancy (WTO)
def calculate_WTO(database, weight_dict):
    total_weight = 0.0
    transaction_weights = []
    for t in database:
        trans_weight = sum(weight_dict.get(item, 0.0) for item in t)
        transaction_weights.append(trans_weight)
        total_weight += trans_weight
    if total_weight == 0:
        logging.error("Total weight is zero. Database may be empty or weights are invalid.")
        print("Error: Total weight is zero.")
        return [0] * len(database)
    if all(w == 0 for w in transaction_weights):
        logging.warning("All transaction weights are zero. Using uniform WTO.")
        return [1.0 / len(database)] * len(database)
    WTO = [tw / total_weight for tw in transaction_weights]
    logging.debug(f"WTO values: {WTO[:5]}... (first 5 transactions)")
    return WTO

# Tính Weighted Support
def calculate_weighted_support(database, WTO, weight_dict, min_ws=0.01):
    ws = defaultdict(float)
    for tid, t in enumerate(database):
        for item in t:
            ws[item] += WTO[tid] * weight_dict[item]
    filtered_ws = {item: w for item, w in ws.items() if w >= min_ws}
    logging.info(f"Number of items after pruning (min_ws={min_ws}): {len(filtered_ws)}")
    print(f"Number of items after pruning (min_ws={min_ws}): {len(filtered_ws)}")
    return filtered_ws

# Xây dựng FP-Tree
def build_fp_tree(database, WTO, weight_dict, min_ws=0.01):
    ws = calculate_weighted_support(database, WTO, weight_dict, min_ws)
    tree = FPTree()
    for tid, t in enumerate(database):
        valid_items = [item for item in t if item in ws]
        if not valid_items:
            continue
        sorted_items = sorted(valid_items, key=lambda x: ws[x], reverse=True)
        tree.add_transaction(sorted_items, WTO[tid], tid)
    return tree, ws

# Hàm tính WIO/WIOUB cho một itemset (dùng trong song song hóa)
def worker_calculate_WIO_WIOUB(args):
    itemset, fp_tree, WTO, weight_dict = args
    itemset = sorted(itemset, key=lambda x: fp_tree.item_counts[x], reverse=True)
    
    # Tính giao của tids cho WIO
    tids = None
    for item in itemset:
        item_tids = set()
        for node in fp_tree.header_table[item]:
            item_tids.update(node.tids)
        tids = item_tids if tids is None else tids & item_tids
    
    # Tính WIO
    WIO = sum(WTO[tid] * sum(weight_dict[item] for item in itemset) / len(itemset) 
              for tid in tids) if tids else 0.0
    
    # Tính hợp của tids cho WIOUB
    WIOUB_tids = set()
    for item in itemset:
        for node in fp_tree.header_table[item]:
            WIOUB_tids.update(node.tids)
    
    # Tính WIOUB
    WIOUB = sum(WTO[tid] * max(weight_dict[item] for item in itemset) 
                for tid in WIOUB_tids) if WIOUB_tids else 0.0
    
    logging.debug(f"Itemset: {itemset}, WIO: {WIO:.3f}, WIOUB: {WIOUB:.3f}, tids: {tids}")
    return itemset, WIO, WIOUB, tids

# Ước lượng WIOUB
def estimate_WIOUB(item, fp_tree, WTO, weight_dict):
    WIOUB_tids = set()
    for node in fp_tree.header_table[item]:
        WIOUB_tids.update(node.tids)
    WIOUB = sum(WTO[tid] * weight_dict[item] for tid in WIOUB_tids) if WIOUB_tids else 0.0
    return WIOUB

# Khai thác tập mục với song song hóa
def fp_growth(fp_tree, WTO, weight_dict, MinWIO, prefix=None, HOI=None):
    if HOI is None:
        HOI = []
    if prefix is None:
        prefix = []
    
    items = [(item, estimate_WIOUB(item, fp_tree, WTO, weight_dict)) 
             for item in fp_tree.header_table.keys() 
             if estimate_WIOUB(item, fp_tree, WTO, weight_dict) >= MinWIO]
    items = sorted(items, key=lambda x: fp_tree.item_counts[x[0]])
    
    logging.info(f"Number of items after WIOUB pruning: {len(items)}")
    
    # Chuẩn bị dữ liệu cho xử lý song song
    tasks = [(prefix + [item], fp_tree, WTO, weight_dict) for item, _ in items]
    
    # Sử dụng multiprocessing Pool
    num_cores = cpu_count()
    logging.info(f"Using {num_cores} CPU cores for parallel processing")
    with Pool(processes=num_cores) as pool:
        results = pool.map(worker_calculate_WIO_WIOUB, tasks)
    
    # Xử lý kết quả
    for itemset, WIO, WIOUB, tids in results:
        if WIO >= MinWIO and WIOUB >= MinWIO:
            HOI.append((itemset, WIO))
            logging.info(f"Added itemset: {itemset}, WIO: {WIO:.3f}, WIOUB: {WIOUB:.3f}")
        
        if WIOUB >= MinWIO:
            cond_pattern_base = []
            for node in fp_tree.header_table[itemset[-1]]:
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
                fp_growth(cond_tree, WTO, weight_dict, MinWIO, itemset, HOI)
    
    return HOI

# Thuật toán HOWI-MTO
def HOWI_MTO(database, MinWIO, weight_dict, min_ws=0.01):
    WTO = calculate_WTO(database, weight_dict)
    fp_tree, ws = build_fp_tree(database, WTO, weight_dict, min_ws)
    
    logging.info("FP-Tree structure (first 10 nodes):")
    fp_tree.print_tree(max_nodes=10)
    
    hoimto_results = fp_growth(fp_tree, WTO, weight_dict, MinWIO)
    return hoimto_results

# Đo bộ nhớ
def get_memory_usage():
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / 1024 / 1024
    mem = max(0.0, mem)
    logging.debug(f"Memory measured: {mem:.5f} MB")
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
    
    min_wio_values = [0.082]  # Giữ nguyên ngưỡng đã tối ưu
    min_ws_values = [0.084]
    
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
            memory_used = max(end_memory - start_memory, 0.0)
            
            results.append({
                'MinWIO': min_wio,
                'min_ws': min_ws,
                'NumItemsets': num_itemsets,
                'Time(s)': time_taken,
                'Memory(MB)': memory_used
            })
            
            logging.info(f"Results: {num_itemsets} itemsets, {time_taken:.3f}s, {memory_used:.3f}MB")
            print(f"Found {num_itemsets} itemsets")
            print(f"Time: {time_taken:.3f} seconds")
            print(f"Memory: {memory_used:.3f} MB")
            if num_itemsets > 0:
                print("Top 5 itemsets:")
                for itemset, WIO in hoimto_results[:5]:
                    print(f"Itemset: {itemset}, WIO: {WIO:.3f}")
    
    results_df = pd.DataFrame(results)
    results_df.to_csv('result_week38_step5_parallel.csv', index=False)
    logging.info("Results saved to result_week38_step5_parallel.csv")
    print("\nResults saved to result_week38_step5_parallel.csv")

if __name__ == "__main__":
    transactions_file = "online_retail_transactions.txt"
    weights_file = "weight_dict.txt"
    tune_parameters(transactions_file, weights_file)