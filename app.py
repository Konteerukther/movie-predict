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
from typing import Dict, Any

# --- 0. Log Function ---
def log(msg: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{level}] {timestamp} | {msg}", file=sys.stdout, flush=True)

app = Flask(__name__)
CORS(app)

# --- 1. Config Path (จุดที่แก้ไข) ---
# เปลี่ยน Default Path เป็น "data" (โฟลเดอร์ในโปรเจกต์) แทน /var/data
# (ถ้าไม่ได้กำหนด Env variable DATA_PATH มันจะใช้ "data" อัตโนมัติ)
PROCESSED_PATH = Path(os.getenv("DATA_PATH", "data")) 
MODEL_PATH = PROCESSED_PATH / "models"
CLEANED_PATH = PROCESSED_PATH / "cleaned"

# --- ฟังก์ชันโหลด SVD Artifacts ---
def load_svd_artifacts(model_dir: Path) -> Dict[str, Any]:
    log(f"Loading SVD artifacts from {model_dir}...") # เพิ่ม log path
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
    except FileNotFoundError as e:
        log(f"SVD Artifacts not found: {e}", "WARN")
        return {}

# --- เริ่มโหลดข้อมูล ---
log(f"Starting app... Data Path: {PROCESSED_PATH.absolute()}") # ดู Path เต็มๆ
log("Loading models... (This might take a while)")

# (ส่วนที่เหลือเหมือนเดิม...)
movies_global = None
ratings_global = None
sim_sparse = None
movie_ids_global = None 
U, Sigma, Vt, svd_user_mean = None, None, None, None
svd_user_index, svd_movie_index = {}, {}
svd_reverse_user_index, svd_reverse_movie_index = {}, {}

try:
    # ใช้ PROCESSED_PATH ที่เราแก้แล้ว
    movies_global = pd.read_csv(CLEANED_PATH / "movies_cleaned_f.csv")
    ratings_global = pd.read_csv(CLEANED_PATH / "ratings_cleaned_f.csv")
    sim_sparse = load_npz(MODEL_PATH / "content_similarity_sparse.npz").tolil()
    
    movie_ids_global = movies_global['movieId'].values 

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
    
    log("--- MODELS LOADED SUCCESSFULLY ---")
except Exception as e:
    log(f"ERROR: Could not load models: {e}", "ERROR")

# --- 2. Helper Functions สำหรับ Recommendation ---

# --- ฟังก์ชันสำหรับ Test 1: Content-Based ---
def get_content_based_recs(movie_title: str, top_n: int = 10) -> pd.DataFrame:
    log(f"Finding Content-Based recommendations for: '{movie_title}'")
    
    # 1. ค้นหา movieId จาก title
    movie_row = movies_global[movies_global['title'].str.contains(movie_title, case=False, na=False)]
    if movie_row.empty:
        log(f"Movie not found: {movie_title}", "WARN")
        return pd.DataFrame()
    
    movie_id = movie_row.iloc[0]['movieId']
    log(f"Found movieId: {movie_id}")

    # 2. ค้นหา index ใน sparse matrix
    idx_arr = np.where(movie_ids_global == movie_id)[0]
    if idx_arr.size == 0:
        log(f"MovieId {movie_id} not found in TF-IDF matrix (no content data).", "WARN")
        return pd.DataFrame()
    
    idx = int(idx_arr[0])

    # 3. ดึง Top-N ที่คล้ายกันจาก sim_sparse
    row_indices = sim_sparse.rows[idx]
    row_data = sim_sparse.data[idx]
    
    if len(row_data) == 0:
        log(f"No similar movies found for index {idx}.", "WARN")
        return pd.DataFrame()

    # 4. Map กลับเป็น movieId และ title
    similar_movie_ids = [movie_ids_global[i] for i in row_indices]
    
    result = movies_global[movies_global.movieId.isin(similar_movie_ids)][['movieId', 'title']].copy()
    score_map = dict(zip(similar_movie_ids, row_data))
    result['similarity_score'] = result['movieId'].map(score_map)
    
    # ไม่เอาตัวเอง และจัดอันดับ
    result = result[result.movieId != movie_id].sort_values('similarity_score', ascending=False)
    
    return result.head(top_n)

# --- ฟังก์ชันสำหรับ Test 2.1: CF (SVD) (Input: User) ---
def get_cf_recs_for_user(user_id: int, top_n: int = 10) -> pd.DataFrame:
    log(f"Finding CF (SVD) recommendations for User {user_id}")
    
    if svd_user_index is None or user_id not in svd_user_index:
        log(f"User ID {user_id} not found in SVD training set.", "WARN")
        return pd.DataFrame()
        
    u_idx = svd_user_index[user_id]
    
    # ทำนายคะแนน (user_vector @ Vt) + user_mean
    user_vector = np.dot(U[u_idx, :], Sigma)  
    preds = np.dot(user_vector, Vt) + svd_user_mean[u_idx]  
    
    # กรองหนังที่เคยดูแล้ว
    seen_movie_ids = set(ratings_global[ratings_global.userId == user_id]['movieId'])
    
    # Map index กลับไปเป็น movieId
    recs = []
    for i in range(len(preds)):
        if i in svd_reverse_movie_index: # ตรวจสอบว่า movie index นี้มีใน mapping
            movie_id = svd_reverse_movie_index[i]
            if movie_id not in seen_movie_ids:
                recs.append((movie_id, preds[i]))

    # จัดอันดับ
    recs.sort(key=lambda x: x[1], reverse=True)
    
    # Join ชื่อหนัง
    top_movie_ids = [mid for mid, score in recs[:top_n]]
    result = movies_global[movies_global.movieId.isin(top_movie_ids)][['movieId', 'title']].copy()
    score_map = dict(recs[:top_n])
    result['predicted_rating'] = result['movieId'].map(score_map)
    
    return result.sort_values('predicted_rating', ascending=False)

# --- ฟังก์ชันสำหรับ Test 2.2: CF (SVD) (Input: Movie) ---
def get_cf_recs_for_movie(movie_title: str, top_n: int = 10) -> pd.DataFrame:
    log(f"Finding best Users for Movie '{movie_title}' using CF (SVD)")
    
    # 1. ค้นหา movieId จาก title
    movie_row = movies_global[movies_global['title'].str.contains(movie_title, case=False, na=False)]
    if movie_row.empty:
        log(f"Movie not found: {movie_title}", "WARN")
        return pd.DataFrame()
    
    movie_id = movie_row.iloc[0]['movieId']
    
    if svd_movie_index is None or movie_id not in svd_movie_index:
        log(f"MovieId {movie_id} not in SVD training set.", "WARN")
        return pd.DataFrame()
        
    m_idx = svd_movie_index[movie_id]

    # 2. ทำนายคะแนน (U @ movie_vector) + user_mean
    movie_factors = Vt[:, m_idx]                 # ได้ vector คุณลักษณะแฝงของหนัง (Shape k,)
    movie_vector = np.dot(Sigma, movie_factors)  # นำไปถ่วงน้ำหนักด้วย Sigma (Shape k,)
    preds_all_users = np.dot(U, movie_vector) + svd_user_mean # (n_users,)
    
    # 3. Map กลับเป็น userId
    recs = []
    for i in range(len(preds_all_users)):
        if i in svd_reverse_user_index:
            user_id = svd_reverse_user_index[i]
            recs.append((user_id, preds_all_users[i]))
            
    # 4. จัดอันดับ
    recs.sort(key=lambda x: x[1], reverse=True)
    
    # 5. สร้าง DataFrame
    top_users = recs[:top_n]
    result = pd.DataFrame(top_users, columns=['userId', 'predicted_rating'])
    
    return result

# --- ฟังก์ชันสำหรับ Test 3: Hybrid ---
# Global variable to cache predictions for a request context
svd_preds_df_global = pd.DataFrame()

def hybrid_score(userId: int, movieId: int, alpha: float = 0.7, top_k: int = 50) -> float:
    try:
        svd_row = svd_preds_df_global[svd_preds_df_global.movieId == movieId]
        svd_score = float(svd_row.pred_rating.values[0]) if not svd_row.empty else np.nan
    except Exception:
        svd_score = np.nan

    if sim_sparse is None or len(movie_ids_global) == 0:
        content_score = np.nan
    else:
        idx_arr = np.where(movie_ids_global == movieId)[0]
        if idx_arr.size == 0:
            content_score = np.nan
        else:
            idx = int(idx_arr[0])
            # Use simple slicing if sim_sparse format allows or catch error
            try:
                # Check if we can access data directly
                # This part depends on matrix structure, assuming it works as in notebook
                row_indices = sim_sparse.rows[idx]
                row_data = sim_sparse.data[idx]
                if len(row_data) == 0:
                    content_score = np.nan
                else:
                    # Approximate content score from top similarities
                    content_score = float(np.nanmean(row_data[:top_k]))
            except:
                 content_score = np.nan

    if np.isnan(svd_score) and np.isnan(content_score): return np.nan
    if np.isnan(svd_score): return content_score
    if np.isnan(content_score): return svd_score
    return alpha * svd_score + (1.0 - alpha) * content_score

def recommend_movies(userId: int, top_n: int = 10, alpha: float = 0.7, top_k_content: int = 50) -> pd.DataFrame:
    global svd_preds_df_global 
    try:
        # คำนวณ SVD preds 'ทั้งหมด' สำหรับ user นี้ 'ครั้งเดียว'
        # Note: get_cf_recs_for_user returns top_n only by default, we need all or many
        # For performance in Hybrid, we might need adjustment, but using what we have:
        # Let's try to fetch more candidates from SVD
        svd_preds_df_global = get_cf_recs_for_user(userId, top_n=500) 
        # เปลี่ยนชื่อคอลัมน์ให้ตรงกับที่ hybrid_score คาดหวัง
        if not svd_preds_df_global.empty:
            svd_preds_df_global = svd_preds_df_global.rename(columns={'predicted_rating': 'pred_rating'})
    except ValueError:
        svd_preds_df_global = pd.DataFrame()
        return pd.DataFrame(columns=['movieId', 'title', 'hybrid_score', 'reason'])

    # หา Candidates (หนังที่ยังไม่เคยดู)
    seen = set(ratings_global.loc[ratings_global.userId == userId, 'movieId'].unique())
    # สุ่มมาเทสซัก 100-200 เรื่องเพื่อความเร็วในการ Demo (แทนที่จะ loop ทั้งหมด)
    # หรือเอาจาก SVD candidates + Content candidates มารวมกัน
    # เพื่อความง่ายใน demo นี้ ใช้ Top SVD + Random
    candidates = list(svd_preds_df_global['movieId'].values) if not svd_preds_df_global.empty else []
    
    # ถ้า candidates น้อยไป ให้เติมเพิ่ม
    if len(candidates) < 50:
        remaining = [mid for mid in movie_ids_global if mid not in seen and mid not in candidates]
        candidates.extend(remaining[:50])

    log(f"Scoring {len(candidates)} candidate movies for user {userId} (Hybrid)...")
    
    scores = []
    for mid in candidates:
        score = hybrid_score(userId, mid, alpha=alpha, top_k=top_k_content)
        if not np.isnan(score):
            scores.append((mid, score))
            
    if len(scores) == 0:
        log(f"No candidate scores for user {userId}", "WARN")
        return pd.DataFrame(columns=['movieId', 'title', 'hybrid_score'])

    scores.sort(key=lambda x: x[1], reverse=True)
    top_scores = scores[:top_n]
    top_movie_ids = [mid for mid, s in top_scores]
    
    result = movies_global[movies_global.movieId.isin(top_movie_ids)][['movieId', 'title']].copy()
    score_map = dict(top_scores)
    result['hybrid_score'] = result['movieId'].map(score_map)
    
    return result.sort_values('hybrid_score', ascending=False).reset_index(drop=True)

log("All helper functions defined.")


# --- 3. สร้าง API Endpoints (นี่คือหัวใจของ Flask) ---

# @app.route(...) คือการสร้าง URL
@app.route("/")
def home():
    return "Welcome to the Recommendation API! (Models Loaded)"

# Endpoint สำหรับ Test 2.1 (CF User)
@app.route("/api/recommend/user/<int:user_id>")
def api_recommend_user(user_id):
    log(f"API call: Get CF recs for User {user_id}")
    try:
        # 1. เรียกฟังก์ชัน Python ที่เรามีอยู่แล้ว
        recs_df = get_cf_recs_for_user(user_id, top_n=10)
        
        # 2. แปลง DataFrame เป็น JSON (ภาษาที่ JavaScript เข้าใจ)
        recs_json = recs_df.to_dict('records')
        
        # 3. ส่ง JSON กลับไป
        return jsonify(recs_json)
    except Exception as e:
        log(f"Error processing request: {e}", "ERROR")
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    # ใช้สำหรับรันในเครื่อง (Local)
    app.run(debug=True, port=5000)