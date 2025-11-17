import os
import sys
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
import numpy as np
from scipy.sparse import load_npz
import pickle
import sqlite3  # <--- เพิ่มไลบรารีนี้

# --- 0. Log Function ---
def log(msg: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{level}] {timestamp} | {msg}", file=sys.stdout, flush=True)

app = Flask(__name__)
CORS(app)

# --- 1. Config Path ---
PROCESSED_PATH = Path(os.getenv("DATA_PATH", "data"))
MODEL_PATH = PROCESSED_PATH / "models"
CLEANED_PATH = PROCESSED_PATH / "cleaned"
DB_FILE = CLEANED_PATH / "ratings.db" # ชี้ไปที่ไฟล์ DB แทน CSV

# --- Helper: โหลด SVD ---
def load_svd_artifacts(model_dir: Path):
    log(f"Loading SVD artifacts from {model_dir}...")
    try:
        U = np.load(model_dir / "svd_U.npy")
        Sigma = np.load(model_dir / "svd_Sigma.npy")
        Vt = np.load(model_dir / "svd_Vt.npy")
        user_mean = np.load(model_dir / "svd_user_mean.npy")
        with open(model_dir / "svd_user_index.pkl", "rb") as f:
            user_index = pickle.load(f)
        with open(model_dir / "svd_movie_index.pkl", "rb") as f:
            movie_index = pickle.load(f)
        with open(model_dir / "svd_reverse_user_index.pkl", "rb") as f:
            reverse_user_index = pickle.load(f)
        with open(model_dir / "svd_reverse_movie_index.pkl", "rb") as f:
            reverse_movie_index = pickle.load(f)
        log("Loaded SVD artifacts successfully.")
        return {
            "U": U, "Sigma": Sigma, "Vt": Vt, "user_mean": user_mean,
            "user_index": user_index, "movie_index": movie_index,
            "reverse_user_index": reverse_user_index, "reverse_movie_index": reverse_movie_index
        }
    except Exception as e:
        log(f"SVD Artifacts Error: {e}", "WARN")
        return {}

# --- Global Variables ---
movies_global = None
sim_sparse = None
movie_ids_global = None
U, Sigma, Vt, svd_user_mean = None, None, None, None
svd_user_index, svd_movie_index = {}, {}
svd_reverse_user_index, svd_reverse_movie_index = {}, {}

# --- Load Data (ตอน Start) ---
log(f"Starting app... Data Path: {PROCESSED_PATH.absolute()}")
try:
    # 1. Movies (ไฟล์เล็ก โหลดเข้า RAM ได้)
    movies_global = pd.read_csv(CLEANED_PATH / "movies_cleaned_f.csv")
    movie_ids_global = movies_global['movieId'].values

    # 2. Ratings -> ⚠️ ไม่โหลดเข้า RAM แล้ว! เราจะใช้ SQLite แทน
    if not DB_FILE.exists():
        log(f"WARNING: Database file not found at {DB_FILE}", "ERROR")
    else:
        log("Database found. Will query from disk.")

    # 3. Similarity Matrix (ไฟล์เล็กพอไหว)
    sim_sparse = load_npz(MODEL_PATH / "content_similarity_sparse.npz").tolil()

    # 4. SVD Artifacts
    svd_artifacts = load_svd_artifacts(MODEL_PATH)
    if svd_artifacts:
        U = svd_artifacts["U"]
        Sigma = svd_artifacts["Sigma"]
        Vt = svd_artifacts["Vt"]
        svd_user_mean = svd_artifacts["user_mean"]
        svd_user_index = svd_artifacts["user_index"]
        svd_movie_index = svd_artifacts["movie_index"]
        svd_reverse_user_index = svd_artifacts["reverse_user_index"]
        svd_reverse_movie_index = svd_artifacts["reverse_movie_index"]

    log("--- MODELS LOADED (RAM Optimized) ---")

except Exception as e:
    log(f"Startup Error: {e}", "ERROR")


# --- Helper Function ใหม่: ดึงหนังที่เคยดูจาก SQLite ---
def get_seen_movies(user_id):
    """Query Database แทนการใช้ Pandas"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # ดึง movieId ทั้งหมดที่ user นี้เคยดู
            cursor.execute("SELECT movieId FROM ratings WHERE userId = ?", (user_id,))
            rows = cursor.fetchall()
            return set([r[0] for r in rows]) # คืนค่าเป็น Set
    except Exception as e:
        log(f"DB Query Error: {e}", "ERROR")
        return set()

# --- (แก้ฟังก์ชัน get_cf_recs_for_user ให้ใช้ get_seen_movies) ---
def get_cf_recs_for_user(user_id: int, top_n: int = 10) -> pd.DataFrame:
    # ... (ส่วนทำนาย SVD เหมือนเดิม) ...
    if svd_user_index is None or user_id not in svd_user_index:
        return pd.DataFrame()
    u_idx = svd_user_index[user_id]
    user_vector = np.dot(U[u_idx, :], Sigma)
    preds = np.dot(user_vector, Vt) + svd_user_mean[u_idx]

    # --- แก้ตรงนี้: เรียกใช้ฟังก์ชัน SQL แทน Pandas ---
    seen_movie_ids = get_seen_movies(user_id) 
    # ----------------------------------------------

    recs = []
    for i in range(len(preds)):
        if i in svd_reverse_movie_index:
            movie_id = svd_reverse_movie_index[i]
            if movie_id not in seen_movie_ids: # เช็กจาก Set ที่ได้จาก DB
                recs.append((movie_id, preds[i]))

    recs.sort(key=lambda x: x[1], reverse=True)
    top_movie_ids = [mid for mid, score in recs[:top_n]]
    result = movies_global[movies_global.movieId.isin(top_movie_ids)][['movieId', 'title']].copy()
    score_map = dict(recs[:top_n])
    result['predicted_rating'] = result['movieId'].map(score_map)
    return result.sort_values('predicted_rating', ascending=False)

# --- (แก้ฟังก์ชัน recommend_movies ด้วย) ---
def recommend_movies(userId: int, top_n: int = 10, alpha: float = 0.7, top_k_content: int = 50) -> pd.DataFrame:
    # ... (ส่วน SVD เหมือนเดิม) ...
    try:
        # ใช้ get_cf_recs_for_user (ซึ่งแก้แล้วให้ใช้ DB) เพื่อหา Top SVD
        # แต่เราต้องการ candidates เยอะหน่อยสำหรับ Hybrid
        # ตรงนี้ SVD ทำงานใน RAM ปกติ ไม่เกี่ยวกับ DB
        pass 
    except:
        pass
    
    # ส่วนหา Candidates ที่ยังไม่เคยดู
    # --- แก้ตรงนี้: ใช้ SQL ---
    seen = get_seen_movies(userId)
    # -----------------------
    
    # (Logic ที่เหลือของ Hybrid เหมือนเดิม ใช้ seen set ในการกรอง)
    # ... (ตัดมาแปะเฉพาะส่วนที่ต้องแก้ ส่วนอื่นใช้ Logic เดิมได้เลย) ...
    # *หมายเหตุ: เพื่อความง่าย คุณสามารถก็อปปี้ Logic Hybrid เดิมมา แล้วเปลี่ยนบรรทัด seen = ... ให้เรียก get_seen_movies(userId) ก็พอครับ

    # (ขออนุญาตละโค้ดส่วนเดิมไว้นะครับ เพื่อความกระชับ)
    return pd.DataFrame() # Placeholder

# --- Routes ---
@app.route("/")
def home(): return "Welcome! (SQLite Version)"

@app.route("/api/recommend/user/<int:user_id>")
def api_recommend_user(user_id):
    try:
        recs_df = get_cf_recs_for_user(user_id, top_n=10)
        return jsonify(recs_df.to_dict('records'))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    app.run(debug=True, port=5000)