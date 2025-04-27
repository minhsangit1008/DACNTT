from collections import defaultdict
import time
import psutil
import os

# Đọc cơ sở dữ liệu và trọng số
def load_weighted_database(file_path, weight_dict):
    database = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                items = line.strip().split()
                items = [item for item in items if ':' not in item]  # Bỏ T1, T2,...
                database.append(set(items))
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return []
    return database

# Tính Transaction Occupancy (TO)
def calculate_TO(database):
    total_items = sum(len(t) for t in database)
    if total_items == 0:
        print("Error: The database is empty.")
        exit()
    return [len(t) / total_items for t in database]

# Tính Weighted Itemset Occupancy (WIO) và Weighted IOUB (WIOUB)
def calculate_WIO_WIOUB(itemset, database, TO, weight_dict):
    tids = [tid for tid, t in enumerate(database) if set(itemset).issubset(t)]
    # Tính WIO
    WIO = sum(TO[tid] * sum(weight_dict[item] for item in itemset) / len(itemset) for tid in tids)
    # Tính WIOUB
    WIOUB = sum(TO[tid] * max(weight_dict[item] for item in itemset if item in t)
                for tid, t in enumerate(database) if any(item in t for item in itemset))
    return WIO, WIOUB, tids

# Thuật toán HOWI-MTO
def HOWI_MTO(database, MinWIO, weight_dict):
    TO = calculate_TO(database)
    HOI = []
    # Tính tần suất cho 1-itemsets
    item_support = defaultdict(list)
    for tid, t in enumerate(database):
        for item in t:
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
    return process.memory_info().rss / 1024 / 1024  # MB

# Chạy thử
if __name__ == "__main__":
    file_path = "transaction_database.txt"
    # Trọng số giả định
    weight_dict = {'a': 0.4, 'b': 0.3, 'c': 0.2, 'd': 0.1}
    database = load_weighted_database(file_path, weight_dict)
    if not database:
        print("Error: Unable to load the database.")
        exit()
    
    MinWIO = 0.3  # Ngưỡng tối thiểu cho WIO
    
    print("HOWI-MTO results:")
    start_time = time.time()
    start_memory = get_memory_usage()
    hoimto_results = HOWI_MTO(database, MinWIO, weight_dict)
    end_time = time.time()
    end_memory = get_memory_usage()
    
    if not hoimto_results:
        print("No itemsets meet the MinWIO threshold.")
    else:
        for itemset, WIO in hoimto_results:
            print(f"Itemset: {itemset}, WIO: {WIO:.3f}")
    
    print(f"Time: {end_time - start_time:.3f} seconds")
    print(f"Memory: {end_memory - start_memory:.3f} MB")