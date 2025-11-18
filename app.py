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
import sqlite3
from typing import Dict, Any

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
DB_FILE = CLEANED_PATH / "ratings.db"
POPULAR_FILE = CLEANED_PATH / "popular_movies.csv" # เพิ่ม Path นี้

# --- 2. Global Variables ---
movies_global = None
popular_movies_global = None # ตัวแปรสำหรับเก็บหนังฮิต
sim_sparse = None
movie_ids_global = None
U, Sigma, Vt, svd_user_mean = None, None, None, None
svd_user_index, svd_movie_index = {}, {}
svd_reverse_user_index, svd_reverse_movie_index = {}, {}
svd_preds_df_global = pd.DataFrame()

# --- 3. Helper: โหลด SVD ---
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

# --- 4. Startup: Load Data ---
log(f"Starting app... Data Path: {PROCESSED_PATH.absolute()}")
try:
    # 4.1 Movies
    movies_global = pd.read_csv(CLEANED_PATH / "movies_cleaned_f.csv")
    movie_ids_global = movies_global['movieId'].values

    # 4.2 Popular Movies (Optional: ถ้ามีไฟล์ให้โหลด ถ้าไม่มีข้าม)
    if POPULAR_FILE.exists():
        popular_movies_global = pd.read_csv(POPULAR_FILE)
        log("Loaded popular_movies.csv successfully.")
    else:
        log("Popular movies file not found, using fallback.")

    # 4.3 Ratings (SQLite Check)
    if not DB_FILE.exists():
        log(f"WARNING: Database file not found at {DB_FILE}", "ERROR")
    else:
        log("Database found. Will query from disk.")

    # 4.4 Similarity Matrix (CSR)
    sim_sparse = load_npz(MODEL_PATH / "content_similarity_sparse.npz")

    # 4.5 SVD Artifacts
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

    log("--- MODELS LOADED (Ready) ---")

except Exception as e:
    log(f"Startup Error: {e}", "ERROR")


# --- 5. Core Logic Functions ---

def get_seen_movies(user_id):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT movieId FROM ratings WHERE userId = ?", (user_id,))
            rows = cursor.fetchall()
            return set([r[0] for r in rows])
    except Exception as e:
        log(f"DB Query Error: {e}", "ERROR")
        return set()

def get_content_based_recs(movie_title: str, top_n: int = 10) -> pd.DataFrame:
    # 1. หา Movie ID
    movie_row = movies_global[movies_global['title'].str.contains(movie_title, case=False, na=False)]
    if movie_row.empty: return pd.DataFrame()
    movie_id = movie_row.iloc[0]['movieId']

    # 2. หา Index ใน Matrix
    idx_arr = np.where(movie_ids_global == movie_id)[0]
    if idx_arr.size == 0: return pd.DataFrame()
    idx = int(idx_arr[0])

    # 3. ดึงข้อมูลจาก CSR Matrix
    try:
        row_vector = sim_sparse[idx] 
        row_indices = row_vector.indices
        row_data = row_vector.data
        
        similar_movie_ids = [movie_ids_global[i] for i in row_indices]
        result = movies_global[movies_global.movieId.isin(similar_movie_ids)][['movieId', 'title']].copy()
        score_map = dict(zip(similar_movie_ids, row_data))
        result['similarity_score'] = result['movieId'].map(score_map)
        
        return result[result.movieId != movie_id].sort_values('similarity_score', ascending=False).head(top_n)
    except Exception as e:
        log(f"Content-Based Error: {e}", "ERROR")
        return pd.DataFrame()

def get_cf_recs_for_user(user_id: int, top_n: int = 10) -> pd.DataFrame:
    if svd_user_index is None or user_id not in svd_user_index:
        # กรณี User ใหม่ -> ส่งหนังฮิตกลับไปแทน (ถ้ามีไฟล์)
        if popular_movies_global is not None:
            log(f"User {user_id} unknown. Returning popular movies.")
            return popular_movies_global.head(top_n)
        return pd.DataFrame()
    
    u_idx = svd_user_index[user_id]
    user_vector = np.dot(U[u_idx, :], Sigma)
    preds = np.dot(user_vector, Vt) + svd_user_mean[u_idx]

    seen_movie_ids = get_seen_movies(user_id)

    recs = []
    for i in range(len(preds)):
        if i in svd_reverse_movie_index:
            movie_id = svd_reverse_movie_index[i]
            if movie_id not in seen_movie_ids:
                recs.append((movie_id, preds[i]))

    recs.sort(key=lambda x: x[1], reverse=True)
    top_movie_ids = [mid for mid, score in recs[:top_n]]
    result = movies_global[movies_global.movieId.isin(top_movie_ids)][['movieId', 'title']].copy()
    score_map = dict(recs[:top_n])
    result['predicted_rating'] = result['movieId'].map(score_map)
    
    return result.sort_values('predicted_rating', ascending=False)

# --- เพิ่มฟังก์ชันนี้สำหรับ Tab 4: Item CF ---
def get_cf_recs_for_movie(movie_title: str, top_n: int = 10) -> pd.DataFrame:
    # 1. Find ID
    movie_row = movies_global[movies_global['title'].str.contains(movie_title, case=False, na=False)]
    if movie_row.empty: return pd.DataFrame()
    movie_id = movie_row.iloc[0]['movieId']

    # 2. Check SVD Index
    if svd_movie_index is None or movie_id not in svd_movie_index: return pd.DataFrame()
    m_idx = svd_movie_index[movie_id]

    # 3. Predict Users
    movie_factors = Vt[:, m_idx] # คุณลักษณะแฝงของหนัง
    # คำนวณคะแนน User ทั้งหมดที่มีต่อหนังเรื่องนี้ = U . Sigma . movie_factors
    user_scores = np.dot(np.dot(U, Sigma), movie_factors) + svd_user_mean
    
    # 4. Top N Users
    top_indices = user_scores.argsort()[::-1][:top_n]
    
    results = []
    for u_idx in top_indices:
        if u_idx in svd_reverse_user_index:
            uid = svd_reverse_user_index[u_idx]
            score = user_scores[u_idx]
            results.append({'userId': uid, 'predicted_rating': score})
            
    return pd.DataFrame(results)
# ---------------------------------------------

def hybrid_score(userId: int, movieId: int, alpha: float = 0.7, top_k: int = 50) -> float:
    try:
        svd_row = svd_preds_df_global[svd_preds_df_global.movieId == movieId]
        svd_score = float(svd_row.pred_rating.values[0]) if not svd_row.empty else np.nan
    except: svd_score = np.nan

    if sim_sparse is None: content_score = np.nan
    else:
        idx_arr = np.where(movie_ids_global == movieId)[0]
        if idx_arr.size == 0: content_score = np.nan
        else:
            idx = int(idx_arr[0])
            try:
                row_vector = sim_sparse[idx]
                row_data = row_vector.data
                if len(row_data) == 0: content_score = np.nan
                else: content_score = float(np.nanmean(row_data[:top_k]))
            except: content_score = np.nan

    if np.isnan(svd_score) and np.isnan(content_score): return np.nan
    if np.isnan(svd_score): return content_score
    if np.isnan(content_score): return svd_score
    return alpha * svd_score + (1.0 - alpha) * content_score

def recommend_movies(userId: int, top_n: int = 10, alpha: float = 0.7) -> pd.DataFrame:
    global svd_preds_df_global
    try:
        svd_preds_df_global = get_cf_recs_for_user(userId, top_n=500)
        if not svd_preds_df_global.empty:
            # เช็กว่าได้ DataFrame ปกติ หรือ Popular Movies (ซึ่งไม่มี predicted_rating)
            if 'predicted_rating' in svd_preds_df_global.columns:
                svd_preds_df_global = svd_preds_df_global.rename(columns={'predicted_rating': 'pred_rating'})
            else:
                # กรณีเป็น Popular Movies (ไม่มีคะแนนทำนาย) ให้คืนค่าไปเลย
                return svd_preds_df_global.head(top_n)
    except: svd_preds_df_global = pd.DataFrame()

    candidates = list(svd_preds_df_global['movieId'].values) if not svd_preds_df_global.empty else []
    if len(candidates) < 50:
        seen = get_seen_movies(userId)
        remaining = [mid for mid in movie_ids_global if mid not in seen and mid not in candidates]
        candidates.extend(remaining[:50])

    scores = []
    for mid in candidates:
        score = hybrid_score(userId, mid, alpha=alpha)
        if not np.isnan(score):
            scores.append((mid, score))
            
    scores.sort(key=lambda x: x[1], reverse=True)
    top_scores = scores[:top_n]
    
    top_movie_ids = [mid for mid, s in top_scores]
    result = movies_global[movies_global.movieId.isin(top_movie_ids)][['movieId', 'title']].copy()
    score_map = dict(top_scores)
    result['hybrid_score'] = result['movieId'].map(score_map)
    
    return result.sort_values('hybrid_score', ascending=False).reset_index(drop=True)

# --- 6. Routes (API Endpoints) ---
@app.route("/")
def home(): return "Welcome to Movie Guru API (Ready for Dashboard)"

# Route 1: Hybrid
@app.route("/api/recommend/user/<int:user_id>") # Legacy endpoint
@app.route("/api/test/hybrid")
def api_recommend_user(user_id=None):
    if user_id is None: user_id = int(request.args.get('id', 0))
    try:
        recs_df = recommend_movies(user_id, top_n=10)
        return jsonify(recs_df.to_dict('records'))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# Route 2: Content-Based
@app.route("/api/test/content")
def test_content():
    try:
        movie_title = request.args.get('movie', '')
        recs = get_content_based_recs(movie_title, top_n=10)
        return jsonify(recs.to_dict('records'))
    except Exception as e: return jsonify({"error": str(e)}), 400

# Route 3: User CF
@app.route("/api/test/cf_user")
def test_cf_user():
    try:
        user_id = int(request.args.get('id', 0))
        recs = get_cf_recs_for_user(user_id, top_n=10)
        return jsonify(recs.to_dict('records'))
    except Exception as e: return jsonify({"error": str(e)}), 400

# Route 4: Item CF
@app.route("/api/test/cf_item")
def test_cf_item():
    try:
        movie_title = request.args.get('movie', '')
        recs = get_cf_recs_for_movie(movie_title, top_n=10)
        return jsonify(recs.to_dict('records'))
    except Exception as e: return jsonify({"error": str(e)}), 400

# Route 5: Search API
@app.route("/api/movies/search")
def search_movies_autocomplete():
    try:
        query = request.args.get('q', '').lower()
        # ถ้าพิมพ์น้อยกว่า 2 ตัวอักษร ไม่ต้องหา (ประหยัดแรง)
        if not query or len(query) < 2:
            return jsonify([])

        # ค้นหาหนังที่มีชื่อตรงกับคำค้น (Case Insensitive)
        # เอาแค่ 10 เรื่องแรกพอ (จะได้ไม่รก)
        matches = movies_global[movies_global['title'].str.lower().str.contains(query, na=False)]
        results = matches[['movieId', 'title']].head(10)
        
        return jsonify(results.to_dict('records'))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
if __name__ == "__main__":
    app.run(debug=True, port=5000)