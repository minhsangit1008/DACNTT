from collections import defaultdict
import time
import psutil
import os

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

    def add_transaction(self, transaction, count):
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

    def print_tree(self, node=None, level=0):
        if node is None:
            node = self.root
        if node.item is not None:
            print("  " * level + f"{node.item}: {node.count:.3f}")
        for child in node.children.values():
            self.print_tree(child, level + 1)

# Đọc cơ sở dữ liệu và trọng số (sửa lại để xử lý đúng định dạng)
def load_weighted_database(file_path, weight_dict):
    database = []
    with open(file_path, 'r') as f:
        # Đọc toàn bộ file (vì dữ liệu chỉ có 1 dòng)
        data = f.read().strip()
        # Tách các giao dịch bằng từ khóa "T[0-9]+:"
        transactions = data.split(' T')[0].split('T')[1:]  # Tách thành ['1: a b c d', '2: a c', ...]
        transactions = [t.strip() for t in transactions]
        for t in transactions:
            parts = t.split(':')
            if len(parts) < 2:
                continue  # Bỏ qua nếu không đúng định dạng
            items = parts[1].strip().split()  # Lấy các mục sau dấu ":"
            database.append(set(items))
    return database

# Tính Transaction Occupancy (TO)
def calculate_TO(database):
    total_items = sum(len(t) for t in database)
    return [len(t) / total_items for t in database]

# Tính Weighted Support để sắp xếp mục
def calculate_weighted_support(database, TO, weight_dict):
    ws = defaultdict(float)
    for tid, t in enumerate(database):
        for item in t:
            ws[item] += TO[tid] * weight_dict[item]
    return ws

# Xây dựng FP-Tree
def build_fp_tree(database, TO, weight_dict):
    ws = calculate_weighted_support(database, TO, weight_dict)
    tree = FPTree()
    for tid, t in enumerate(database):
        sorted_items = sorted(t, key=lambda x: ws[x], reverse=True)
        tree.add_transaction(sorted_items, TO[tid])
    return tree

# Tính WIO và WIOUB
def calculate_WIO_WIOUB(itemset, database, TO, weight_dict):
    tids = [tid for tid, t in enumerate(database) if set(itemset).issubset(t)]
    WIO = sum(TO[tid] * sum(weight_dict[item] for item in itemset) / len(itemset) for tid in tids)
    WIOUB = sum(TO[tid] * max(weight_dict[item] for item in itemset if item in t)
                for tid, t in enumerate(database) if any(item in t for item in itemset))
    return WIO, WIOUB, tids

# Thuật toán HOWI-MTO với FP-Tree
def HOWI_MTO(database, MinWIO, weight_dict):
    TO = calculate_TO(database)
    fp_tree = build_fp_tree(database, TO, weight_dict)
    print("FP-Tree structure:")
    fp_tree.print_tree()
    
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
            WIO, WIOUB, tids = calculate_WIO_WIOUB(itemset, database, TO, weight_dict)
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

# Đo bộ nhớ
def get_memory_usage():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

# Chạy thử
if __name__ == "__main__":
    file_path = "transaction_database.txt"
    weight_dict = {'a': 0.4, 'b': 0.3, 'c': 0.2, 'd': 0.1}
    database = load_weighted_database(file_path, weight_dict)
    MinWIO = 0.3
    
    print("HOWI-MTO results (with FP-Tree):")
    start_time = time.time()
    start_memory = get_memory_usage()
    hoimto_results = HOWI_MTO(database, MinWIO, weight_dict)
    end_time = time.time()
    end_memory = get_memory_usage()
    
    for itemset, WIO in hoimto_results:
        print(f"Itemset: {itemset}, WIO: {WIO:.3f}")
    print(f"Time: {end_time - start_time:.3f} seconds")
    print(f"Memory: {end_memory - start_memory:.3f} MB")













# from collections import defaultdict
# import time
# import psutil
# import os
# import json

# # Lớp nút trong FP-Tree
# class FPNode:
#     def __init__(self, item, count, parent):
#         self.item = item
#         self.count = count
#         self.parent = parent
#         self.children = {}
#         self.node_link = None

# class FPTree:
#     def __init__(self):
#         self.root = FPNode(None, 0, None)
#         self.header_table = defaultdict(list)
#         self.item_counts = defaultdict(float)

#     def add_transaction(self, transaction, count):
#         current = self.root
#         for item in transaction:
#             self.item_counts[item] += count
#             if item in current.children:
#                 current.children[item].count += count
#             else:
#                 new_node = FPNode(item, count, current)
#                 current.children[item] = new_node
#                 self.header_table[item].append(new_node)
#             current = current.children[item]

#     def print_tree(self, node=None, level=0):
#         if node is None:
#             node = self.root
#         if node.item is not None:
#             print("  " * level + f"{node.item}: {node.count:.3f}")
#         for child in node.children.values():
#             self.print_tree(child, level + 1)

# # Đọc cơ sở dữ liệu từ file (chuẩn với online_retail_transactions.txt)
# def load_weighted_database(file_path, weight_dict):
#     database = []
#     with open(file_path, 'r') as f:
#         for line in f:
#             parts = line.strip().split(':')
#             if len(parts) < 2:
#                 continue
#             items = parts[1].strip().split()
#             valid_items = [item for item in items if item in weight_dict]
#             if not valid_items:
#                 continue
#             database.append(set(valid_items))
#     return database

# # Đọc weight_dict từ file JSON
# def load_weight_dict(file_path):
#     with open(file_path, 'r') as f:
#         return json.load(f)

# # Tính Transaction Occupancy (TO)
# def calculate_TO(database):
#     total_items = sum(len(t) for t in database)
#     return [len(t) / total_items for t in database] if total_items > 0 else [0] * len(database)

# # Tính Weighted Support
# def calculate_weighted_support(database, TO, weight_dict):
#     ws = defaultdict(float)
#     for tid, t in enumerate(database):
#         for item in t:
#             ws[item] += TO[tid] * weight_dict[item]
#     return ws

# # Xây dựng FP-Tree
# def build_fp_tree(database, TO, weight_dict):
#     ws = calculate_weighted_support(database, TO, weight_dict)
#     tree = FPTree()
#     for tid, t in enumerate(database):
#         sorted_items = sorted(t, key=lambda x: ws[x], reverse=True)
#         tree.add_transaction(sorted_items, TO[tid])
#     return tree

# # Tính WIO và WIOUB
# def calculate_WIO_WIOUB(itemset, database, TO, weight_dict):
#     tids = [tid for tid, t in enumerate(database) if set(itemset).issubset(t)]
#     WIO = sum(TO[tid] * sum(weight_dict[item] for item in itemset) / len(itemset) for tid in tids)
#     WIOUB = sum(TO[tid] * max(weight_dict[item] for item in itemset if item in t)
#                 for tid, t in enumerate(database) if any(item in t for item in itemset))
#     return WIO, WIOUB, tids

# # Thuật toán HOWI-MTO
# def HOWI_MTO(database, MinWIO, weight_dict):
#     TO = calculate_TO(database)
#     fp_tree = build_fp_tree(database, TO, weight_dict)
#     print("FP-Tree structure:")
#     fp_tree.print_tree()

#     HOI = []
#     item_support = defaultdict(list)
#     for tid, t in enumerate(database):
#         for item in t:
#             item_support[item].append(tid)

#     candidates = [[item] for item in item_support]
#     k = 1
#     while candidates:
#         next_candidates = []
#         for itemset in candidates:
#             WIO, WIOUB, tids = calculate_WIO_WIOUB(itemset, database, TO, weight_dict)
#             if WIOUB >= MinWIO:
#                 if WIO >= MinWIO:
#                     HOI.append((itemset, WIO))
#                     if k == 1:
#                         next_candidates.extend([[itemset[0], new_item] for new_item in item_support if new_item > itemset[0]])
#                     else:
#                         for other in candidates:
#                             if other[:k-1] == itemset[:k-1] and other[k-1] > itemset[k-1]:
#                                 next_candidates.append(itemset + [other[k-1]])
#         candidates = next_candidates
#         k += 1

#     return HOI

# # Đo bộ nhớ
# def get_memory_usage():
#     process = psutil.Process(os.getpid())
#     return process.memory_info().rss / 1024 / 1024

# # Chạy thử
# if __name__ == "__main__":
#     transactions_file = "online_retail_transactions.txt"
#     weights_file = "weight_dict.txt"
#     MinWIO = 0.05

#     # Load dữ liệu
#     weight_dict = load_weight_dict(weights_file)
#     database = load_weighted_database(transactions_file, weight_dict)

#     print("HOWI-MTO results (with FP-Tree):")
#     start_time = time.time()
#     start_memory = get_memory_usage()
#     hoimto_results = HOWI_MTO(database, MinWIO, weight_dict)
#     end_time = time.time()
#     end_memory = get_memory_usage()

#     print(f"Found {len(hoimto_results)} itemsets")
#     for itemset, WIO in hoimto_results[:10]:  # In 10 tập mục đầu tiên
#         print(f"Itemset: {itemset}, WIO: {WIO:.3f}")
#     print(f"Time: {end_time - start_time:.3f} seconds")
#     print(f"Memory: {end_memory - start_memory:.3f} MB")
