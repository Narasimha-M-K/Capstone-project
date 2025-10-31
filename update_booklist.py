import kagglehub
import pandas as pd
import os

# Step 1: Download the dataset using kagglehub
path = kagglehub.dataset_download("marianadeem755/bestsellers-unveiled-global-top-selling-books")
print("Path to dataset files:", path)

# Step 2: Find the CSV file inside the downloaded folder
# (The Kaggle dataset may contain multiple files, so we look for any .csv file)
csv_files = [f for f in os.listdir(path) if f.endswith('.csv')]
if not csv_files:
    raise FileNotFoundError("No CSV files found in the dataset folder.")

dataset_path = os.path.join(path, csv_files[0])
print("Using dataset file:", dataset_path)

# Step 3: Load the dataset with pandas
df = pd.read_csv(dataset_path)

# Step 4: Inspect column names (to confirm exact names)
print("Columns in dataset:", df.columns.tolist())

# Step 5: Extract only the relevant columns
# (adjust the names depending on the dataset’s actual column headers)
# For example, suppose columns are ['Book Title', 'Author', 'Genre', 'Year', ...]
books_df = df[['Title', 'Author']]
books_df.to_csv('books.csv', mode='a', header=False, index=False)

print("✅ Saved selected columns to books.csv")
