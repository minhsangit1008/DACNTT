import pandas as pd
import json

def preprocess_online_retail(input_file, old_weight_dict_file, output_transactions_file, max_transactions=10000, min_item_freq=5):
    # Đọc file Excel
    df = pd.read_excel(input_file)
    
    # Loại bỏ giao dịch không hợp lệ
    df = df[df['Quantity'] > 0]
    df = df.dropna(subset=['InvoiceNo', 'StockCode'])
    
    # Chuyển StockCode thành chuỗi và chuẩn hóa
    df['StockCode'] = df['StockCode'].astype(str).str.upper()
    
    # Loại bỏ item hiếm
    item_counts = df['StockCode'].value_counts()
    valid_items = set(item_counts[item_counts >= min_item_freq].index)
    df = df[df['StockCode'].isin(valid_items)]
    
    # Nhóm theo InvoiceNo để tạo giao dịch
    transactions = df.groupby('InvoiceNo')['StockCode'].apply(set).reset_index()
    transaction_list = transactions['StockCode'].tolist()
    
    # Giới hạn số giao dịch
    transaction_list = transaction_list[:min(max_transactions, len(transaction_list))]
    
    # Đọc weight_dict từ bước 1
    try:
        with open(old_weight_dict_file, 'r') as f:
            weight_dict = json.load(f)
    except FileNotFoundError:
        print(f"Error: {old_weight_dict_file} not found.")
        return
    
    # Lưu giao dịch, chỉ giữ item có trong weight_dict
    with open(output_transactions_file, 'w') as f:
        for i, t in enumerate(transaction_list, 1):
            items = [item for item in t if item in weight_dict]
            if items:
                f.write(f"T{i}: {' '.join(items)}\n")
    
    # Thống kê
    print(f"Transactions saved to {output_transactions_file}")
    print(f"Number of transactions: {sum(1 for line in open(output_transactions_file))}")
    print(f"Number of unique items in transactions: {len(set(item for line in open(output_transactions_file) for item in line.strip().split(':')[1].split() if ':' in line))}")
    print(f"Sample transactions: {[line.strip() for line in open(output_transactions_file).readlines()[:5]]}")

if __name__ == "__main__":
    input_file = "Online Retail.xlsx"
    old_weight_dict_file = "weight_dict.txt"  # File weight_dict.txt từ bước 1
    output_transactions_file = "online_retail_transactions.txt"
    
    preprocess_online_retail(input_file, old_weight_dict_file, output_transactions_file, max_transactions=10000)
    
    
    
    
    
