from HOIM import HOIM, load_database
from HOIMTO import HOIMTO, calculate_TO
import time
import psutil
import os

# Đo bộ nhớ
def get_memory_usage():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024  # MB

# Chạy và so sánh
if __name__ == "__main__":
    file_path = "transaction_database.txt"
    database = load_database(file_path)
    MinIO = 0.3

    # Chạy HOIM
    print("HOIM results:")
    start_time = time.time()
    start_memory = get_memory_usage()
    hoim_results = HOIM(database, MinIO)
    end_time = time.time()
    end_memory = get_memory_usage()
    for itemset, IO in hoim_results:
        print(f"Itemset: {itemset}, IO: {IO:.3f}")
    print(f"Time: {end_time - start_time:.3f} seconds")
    print(f"Memory: {end_memory - start_memory:.3f} MB")
    
    print("\nHOIMTO results:")
    start_time = time.time()
    start_memory = get_memory_usage()
    hoimto_results = HOIMTO(database, MinIO)
    end_time = time.time()
    end_memory = get_memory_usage()
    for itemset, IO in hoimto_results:
        print(f"Itemset: {itemset}, IO: {IO:.3f}")
    print(f"Time: {end_time - start_time:.3f} seconds")
    print(f"Memory: {end_memory - start_memory:.3f} MB")