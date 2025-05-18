from collections import defaultdict
import time
import psutil
import os
import json
import logging

# Thiết lập logging
logging.basicConfig(level=logging.INFO, filename='howi_mto_apriori.log', filemode='w',
                    format='%(asctime)s - %(levelname)s - %(message)s')

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

# Tính Weighted Support để cắt tỉa
def calculate_weighted_support(database, TO, weight_dict, min_ws):
    ws = defaultdict(float)
    for tid, t in enumerate(database):
        for item in t:
            ws[item] += TO[tid] * weight_dict[item]
    filtered_ws = {item: w for item, w in ws.items() if w >= min_ws}
    logging.info(f"Number of items after pruning (min_ws={min_ws}): {len(filtered_ws)}")
    print(f"Number of items after pruning (min_ws={min_ws}): {len(filtered_ws)}")
    return filtered_ws

# Tính Weighted Itemset Occupancy (WIO) và Weighted IOUB (WIOUB)
def calculate_WIO_WIOUB(itemset, database, TO, weight_dict):
    tids = [tid for tid, t in enumerate(database) if set(itemset).issubset(t)]
    # Tính WIO
    WIO = sum(TO[tid] * sum(weight_dict[item] for item in itemset) / len(itemset) for tid in tids)
    # Tính WIOUB
    WIOUB = sum(TO[tid] * max(weight_dict[item] for item in itemset if item in t)
                for tid, t in enumerate(database) if any(item in t for item in itemset))
    logging.debug(f"Itemset: {itemset}, WIO: {WIO:.3f}, WIOUB: {WIOUB:.3f}, tids: {tids}")
    return WIO, WIOUB, tids

# Thuật toán HOWI-MTO với cắt tỉa min_ws
def HOWI_MTO(database, MinWIO, weight_dict, min_ws=0.1):
    TO = calculate_TO(database)
    # Tính Weighted Support và cắt tỉa
    ws = calculate_weighted_support(database, TO, weight_dict, min_ws)
    HOI = []
    # Tính tần suất cho 1-itemsets
    item_support = defaultdict(list)
    for tid, t in enumerate(database):
        for item in t:
            if item in ws:
                item_support[item].append(tid)
    
    # Kiểm tra 1-itemsets
    candidates = [[item] for item in item_support]
    k = 1
    while candidates:
        next_candidates = []
        for itemset in candidates:
            WIO, WIOUB, tids = calculate_WIO_WIOUB(itemset, database, TO, weight_dict)
            if WIOUB >= MinWIO:  # Cắt tỉa dựa trên WIOUB
                if WIO >= MinWIO:
                    HOI.append((itemset, WIO))
                    # Sinh k+1 itemsets
                    if k == 1:
                        next_candidates.extend([[itemset[0], new_item] for new_item in item_support if new_item > itemset[0]])
                    else:
                        for other in candidates:
                            if other[:k-1] == itemset[:k-1] and other[k-1] > itemset[k-1]:
                                next_candidates.append(itemset + [other[k-1]])
        candidates = next_candidates
        k += 1
    
    return HOI

# Đo bộ nhớ
def get_memory_usage():
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / 1024 / 1024
    return max(mem, 0.0)  # Tránh giá trị âm

# Chạy thử
if __name__ == "__main__":
    transactions_file = "online_retail_transactions.txt"
    weights_file = "weight_dict.txt"
    
    # Đọc weight_dict
    weight_dict = load_weight_dict(weights_file)
    if not weight_dict:
        logging.error("Exiting due to weight_dict load failure.")
        print("Error: Unable to load weight_dict. Exiting.")
        exit()
    
    # Đọc database
    database = load_weighted_database(transactions_file, weight_dict)
    if not database:
        logging.error("Exiting due to database load failure.")
        print("Error: Unable to load the database. Exiting.")
        exit()
    
    MinWIO = 0.2  # Ngưỡng từ thử nghiệm FP-Tree
    min_ws = 0.1  # Ngưỡng cắt tỉa
    
    logging.info(f"Running HOWI-MTO with MinWIO={MinWIO}, min_ws={min_ws}")
    print(f"HOWI-MTO (Apriori) with MinWIO={MinWIO}, min_ws={min_ws}:")
    
    start_time = time.time()
    start_memory = get_memory_usage()
    hoimto_results = HOWI_MTO(database, MinWIO, weight_dict, min_ws)
    end_time = time.time()
    end_memory = get_memory_usage()
    
    # Lưu kết quả
    output_file = "apriori_itemsets.txt"
    with open(output_file, 'w') as f:
        if not hoimto_results:
            f.write("No itemsets meet the MinWIO threshold.\n")
            print("No itemsets meet the MinWIO threshold.")
        else:
            for itemset, WIO in hoimto_results:
                f.write(f"Itemset: {itemset}, WIO: {WIO:.3f}\n")
                print(f"Itemset: {itemset}, WIO: {WIO:.3f}")
    
    time_taken = end_time - start_time
    memory_used = end_memory - start_memory
    logging.info(f"Found {len(hoimto_results)} itemsets, Time: {time_taken:.3f}s, Memory: {memory_used:.3f}MB")
    print(f"Found {len(hoimto_results)} itemsets")
    print(f"Time: {time_taken:.3f} seconds")
    print(f"Memory: {memory_used:.3f} MB")
    print(f"Results saved to {output_file}")