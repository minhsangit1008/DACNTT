import pandas as pd
import random
import json

def preprocess_online_retail(input_file, output_transactions_file, output_weights_file, max_transactions=1000):
    # Đọc file Excel
    df = pd.read_excel(input_file)

    # Loại bỏ giao dịch không hợp lệ
    df = df[df['Quantity'] > 0]
    df = df.dropna(subset=['InvoiceNo', 'StockCode'])

    # Chuyển đổi thành định dạng giao dịch
    transactions = df.groupby('InvoiceNo')['StockCode'].apply(set).reset_index()
    transaction_list = transactions['StockCode'].tolist()

    # Giới hạn số giao dịch để xuất ra file
    transaction_list_to_save = transaction_list[:max_transactions]

    # Lưu vào file giao dịch
    with open(output_transactions_file, 'w') as f:
        for i, t in enumerate(transaction_list_to_save, 1):
            items = [str(item).upper() for item in t]
            f.write(f"T{i}: {' '.join(items)}\n")

    # Sinh weight_dict từ toàn bộ dữ liệu (không giới hạn)
    all_items = set(df['StockCode'].astype(str).str.upper())
    weight_dict = {item: round(random.uniform(0.1, 1.0), 2) for item in all_items}

    # Lưu weight_dict
    with open(output_weights_file, 'w') as f:
        json.dump(weight_dict, f)

    return weight_dict

if __name__ == "__main__":
    input_file = "Online Retail.xlsx"
    output_transactions_file = "online_retail_transactions.txt"
    output_weights_file = "weight_dict.txt"

    weight_dict = preprocess_online_retail(input_file, output_transactions_file, output_weights_file, max_transactions=1000)
    print(f"Transactions saved to {output_transactions_file}")
    print(f"Weight dictionary saved to {output_weights_file}")
    print(f"Number of transactions: {sum(1 for line in open(output_transactions_file))}")
    print(f"Number of unique items in weight_dict: {len(weight_dict)}")
    print("Sample weight_dict:", dict(list(weight_dict.items())[:5]))
    print("Sample transactions:", [line.strip() for line in open(output_transactions_file).readlines()[:5]])