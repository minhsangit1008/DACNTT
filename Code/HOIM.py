from collections import defaultdict
import time
import psutil
import os

# Đọc dữ liệu từ file
def load_database(file_path):
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found!")
        return []
    database = []
    with open(file_path, 'r') as f:
        for line in f:
            items = line.strip().split()[1:]  # Bỏ T1, T2,...
            database.append(set(items))
    print("Loaded database:", database)  # Debug: In dữ liệu đọc được
    return database

# Thuật toán HOIM
def HOIM(database, MinIO):
    if not database:
        print("Error: Database is empty!")
        return []
    
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
            tids = [tid for tid, t in enumerate(database) if set(itemset).issubset(t)]
            IO = sum(1 / len(database[tid]) for tid in tids)
            print(f"Itemset: {itemset}, IO: {IO:.3f}")  # Debug: In IO của mỗi tập mục
            if IO >= MinIO:
                HOI.append((itemset, IO))
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
    # Đường dẫn đến file dữ liệu
    file_path = "transaction_database.txt"
    database = load_database(file_path)
    MinIO = 0.1  # Giảm MinIO để dễ kiểm tra
    
    print("\nHOIM results:")
    start_time = time.time()
    start_memory = get_memory_usage()
    hoim_results = HOIM(database, MinIO)
    end_time = time.time()
    end_memory = get_memory_usage()
    
    if hoim_results:
        for itemset, IO in hoim_results:
            print(f"Itemset: {itemset}, IO: {IO:.3f}")
    else:
        print("No High-Occupancy Itemsets found!")
    print(f"Time: {end_time - start_time:.3f} seconds")
    print(f"Memory: {end_memory - start_memory:.3f} MB")