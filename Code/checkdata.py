import json

# Kiểm tra transactions file
def check_transactions(file_path):
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        num_transactions = len(lines)
        valid_lines = [line for line in lines if ':' in line]
        num_valid = len(valid_lines)
        if num_valid == 0:
            print("Error: No valid transactions (format 'tid: item1 item2 ...').")
            return
        
        lengths = [len(line.strip().split(':')[1].split()) for line in valid_lines]
        items = set()
        for line in valid_lines:
            items.update(line.strip().split(':')[1].split())
        
        print(f"Number of transactions: {num_transactions}")
        print(f"Number of valid transactions: {num_valid}")
        print(f"Average items per transaction: {sum(lengths)/len(lengths):.2f}")
        print(f"Unique items: {len(items)}")
        print(f"Sample items: {list(items)[:10]}")
        print(f"Sample transaction: {valid_lines[0].strip()}")
        
        return items
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return set()

# Kiểm tra weight_dict file
def check_weight_dict(trans_file, weight_file):
    try:
        with open(weight_file, 'r') as f:
            weight_dict = json.load(f)
        
        trans_items = check_transactions(trans_file)
        missing = trans_items - set(weight_dict.keys())
        
        print(f"\nWeight dict stats:")
        print(f"Number of items in weight_dict: {len(weight_dict)}")
        print(f"Sample weights: {dict(list(weight_dict.items())[:5])}")
        print(f"Missing weights for {len(missing)} items: {list(missing)[:10]}")
        
        if missing:
            print("Warning: Some transaction items lack weights, leading to data loss.")
    except FileNotFoundError:
        print(f"Error: File '{weight_file}' not found.")
    except json.JSONDecodeError:
        print(f"Error: File '{weight_file}' contains invalid JSON.")

if __name__ == "__main__":
    trans_file = "online_retail_transactions.txt"
    weight_file = "weight_dict.txt"
    check_weight_dict(trans_file, weight_file)