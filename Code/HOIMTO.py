from collections import defaultdict
import time
import psutil
import os

# Đọc dữ liệu từ file
def load_database(file_path):
    database = []
    with open(file_path, 'r') as f:
        for line in f:
            items = line.strip().split()[1:]  # Bỏ T1, T2,...
            database.append(set(items))
    return database

# Tính Transaction Occupancy (TO)
def calculate_TO(database):
    total_items = sum(len(t) for t in database)
    return [len(t) / total_items for t in database]

# Tính Itemset Occupancy (IO) và IOUB
def calculate_IO_IOUB(itemset, database, TO):
    tids = [tid for tid, t in enumerate(database) if set(itemset).issubset(t)]
    IO = sum(TO[tid] for tid in tids)
    # IOUB: Giả định đơn giản là tổng TO của các giao dịch chứa ít nhất một mục trong itemset
    IOUB = sum(TO[tid] for tid, t in enumerate(database) if any(item in t for item in itemset))
    return IO, IOUB, tids

# Thuật toán HOIMTO
def HOIMTO(database, MinIO):
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
            IO, IOUB, tids = calculate_IO_IOUB(itemset, database, TO)
            if IOUB >= MinIO:  # Cắt tỉa dựa trên IOUB
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
    MinIO = 0.3  # Ngưỡng tối thiểu cho IO
    
    print("HOIMTO results:")
    start_time = time.time()
    start_memory = get_memory_usage()
    hoimto_results = HOIMTO(database, MinIO)
    end_time = time.time()
    end_memory = get_memory_usage()
    
    for itemset, IO in hoimto_results:
        print(f"Itemset: {itemset}, IO: {IO:.3f}")
    print(f"Time: {end_time - start_time:.3f} seconds")
    print(f"Memory: {end_memory - start_memory:.3f} MB")