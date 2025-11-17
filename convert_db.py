import pandas as pd
import sqlite3
from pathlib import Path

# ตั้งค่า Path
CSV_PATH = Path("processed/cleaned/ratings_cleaned_f.csv")
DB_PATH = Path("processed/cleaned/ratings.db") # เราจะสร้างไฟล์นี้

print(f"🚀 กำลังแปลง {CSV_PATH} เป็น SQLite Database...")

# 1. เชื่อมต่อ Database (จะสร้างไฟล์ใหม่ให้เอง)
conn = sqlite3.connect(DB_PATH)

# 2. อ่าน CSV ทีละก้อน (Chunk) เพื่อไม่ให้ RAM เครื่องคุณเต็ม
chunk_size = 1000000  # ทีละ 1 ล้านแถว
total_rows = 0

# อ่านเฉพาะ userId และ movieId (ประหยัดที่)
for chunk in pd.read_csv(CSV_PATH, chunksize=chunk_size, usecols=['userId', 'movieId']):
    # เขียนลง Database
    chunk.to_sql('ratings', conn, if_exists='append', index=False)
    total_rows += len(chunk)
    print(f"   ...บันทึกแล้ว {total_rows:,} แถว")

print("📦 สร้าง Index เพื่อให้ค้นหาเร็วๆ...")
conn.execute("CREATE INDEX idx_user ON ratings(userId)")
conn.close()

print(f"✅ เสร็จสมบูรณ์! ได้ไฟล์ {DB_PATH}")