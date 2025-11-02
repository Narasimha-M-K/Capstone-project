import pandas as pd
import os

# === CONFIGURATION ===
BOOKS_CSV_PATH = "books.csv"
NEW_DATASET_PATH = "Books_Data_Clean.csv"   # 👈 change this to your downloaded Kaggle CSV name

# === STEP 1: LOAD EXISTING BOOKS FILE ===
if os.path.exists(BOOKS_CSV_PATH):
    existing_books = pd.read_csv(BOOKS_CSV_PATH)
else:
    existing_books = pd.DataFrame(columns=["book_id", "title", "author", "library_id"])

# Clean up any unnamed/blank columns
existing_books = existing_books.loc[:, ~existing_books.columns.str.contains('^Unnamed')]
existing_books.columns = existing_books.columns.str.strip().str.lower()

# === STEP 2: LOAD NEW DATASET ===
df = pd.read_csv(NEW_DATASET_PATH)

# Detect title & author columns
possible_title_cols = [c for c in df.columns if "title" in c.lower() or "book" in c.lower()]
possible_author_cols = [c for c in df.columns if "author" in c.lower()]

if not possible_title_cols:
    raise ValueError("❌ Could not find any column that looks like a book title.")
if not possible_author_cols:
    raise ValueError("❌ Could not find any column that looks like an author name.")

title_col = possible_title_cols[0]
author_col = possible_author_cols[0]

new_books = df[[title_col, author_col]].copy()
new_books.columns = ["title", "author"]

# Clean text formatting
new_books["title"] = new_books["title"].astype(str).str.strip()
new_books["author"] = new_books["author"].astype(str).str.strip()

# === STEP 3: ASSIGN UNIQUE LIBRARY IDS ===
if len(existing_books) > 0 and "library_id" in existing_books.columns:
    existing_books["library_id"] = pd.to_numeric(existing_books["library_id"], errors="coerce").fillna(1000).astype(int)
    start_lib_id = int(existing_books["library_id"].max()) + 1
else:
    start_lib_id = 1000

new_books["library_id"] = range(start_lib_id, start_lib_id + len(new_books))

# === STEP 4: MERGE AND REMOVE DUPLICATES ===
combined = pd.concat([existing_books, new_books], ignore_index=True)
combined = combined.drop_duplicates(subset=["title", "author"], keep="first").reset_index(drop=True)

# ✅ Remove existing book_id column (fix for your error)
if "book_id" in combined.columns:
    combined = combined.drop(columns=["book_id"])

# === STEP 5: REASSIGN BOOK IDs FROM 1 ===
combined.insert(0, "book_id", range(1, len(combined) + 1))

# === STEP 6: REORDER & SAVE ===
combined = combined[["book_id", "title", "author", "library_id"]]
combined.to_csv(BOOKS_CSV_PATH, index=False)

print("✅ books.csv updated successfully!")
print(f"📚 Total books in file: {len(combined)}")
print(f"📂 File saved at: {os.path.abspath(BOOKS_CSV_PATH)}")
