import os
from pathlib import Path
from flask import Flask, jsonify
import pandas as pd
import numpy as np
from scipy.sparse import load_npz
import pickle

# --- 0. ตั้งค่า ---
app = Flask(__name__)

# --- 1. โหลดโมเดล (ส่วนนี้จะถูกเรียก 'ครั้งเดียว' ตอนเปิดเซิร์ฟเวอร์) ---
# เราจะ 'สมมติ' ว่าไฟล์ 2GB ของเราถูกโหลดมาอยู่ที่ '/var/data' (เดี๋ยว Render จะทำตรงนี้ให้)
PROCESSED_PATH = Path(os.getenv("DATA_PATH", "/var/data/processed"))
MODEL_PATH = PROCESSED_PATH / "models"
CLEANED_PATH = PROCESSED_PATH / "cleaned"

log("Loading models... (This might take a while)")

try:
    # โหลดไฟล์ 2GB จากดิสก์ของ Render
    movies_global = pd.read_csv(CLEANED_PATH / "movies_cleaned_f.csv")
    ratings_global = pd.read_csv(CLEANED_PATH / "ratings_cleaned_f.csv")
    sim_sparse = load_npz(MODEL_PATH / "content_similarity_sparse.npz").tolil()
    
    # (เพิ่มโค้ดโหลด SVD Artifacts (U, Sigma, Vt, Mappings) จาก MODEL_PATH ที่นี่)
    # artifacts = load_svd_artifacts(MODEL_PATH)
    # ...
    
    log("--- MODELS LOADED SUCCESSFULLY ---")
except Exception as e:
    log(f"ERROR: Could not load models: {e}", "ERROR")

# --- 2. คัดลอก Helper Functions จาก Deployment.ipynb ---
# (คัดลอก get_content_based_recs, get_cf_recs_for_user, ฯลฯ มาวางที่นี่)
# ...
# --- ฟังก์ชันสำหรับโหลด SVD Artifacts ---
def load_svd_artifacts(model_dir: Path) -> Dict[str, Any]:
    log("Loading SVD artifacts from disk...")
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
        
    log("Loaded SVD artifacts")
    return {
        "U": U, "Sigma": Sigma, "Vt": Vt, "user_mean": user_mean,
        "user_index": user_index, "movie_index": movie_index,
        "reverse_user_index": reverse_user_index, "reverse_movie_index": reverse_movie_index
    }

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
    
    if user_id not in svd_user_index:
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
    
    if movie_id not in svd_movie_index:
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

# --- ฟังก์ชันสำหรับ Test 3: Hybrid (เหมือนเดิม) ---
# (หมายเหตุ: 2 ฟังก์ชันนี้ถูกคัดลอกมาจาก Cell 3 ของคำตอบก่อนหน้า)
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
            row = sim_sparse.rows[idx]
            data = sim_sparse.data[idx]
            if len(data) == 0:
                content_score = np.nan
            else:
                content_score = float(np.nanmean(data[:top_k]))

    if np.isnan(svd_score) and np.isnan(content_score): return np.nan
    if np.isnan(svd_score): return content_score
    if np.isnan(content_score): return svd_score
    return alpha * svd_score + (1.0 - alpha) * content_score

def recommend_movies(userId: int, top_n: int = 10, alpha: float = 0.7, top_k_content: int = 50) -> pd.DataFrame:
    global svd_preds_df_global 
    try:
        # คำนวณ SVD preds 'ทั้งหมด' สำหรับ user นี้ 'ครั้งเดียว'
        svd_preds_df_global = get_cf_recs_for_user(userId, top_n=len(svd_movie_index))
        # เปลี่ยนชื่อคอลัมน์ให้ตรงกับที่ hybrid_score คาดหวัง
        svd_preds_df_global = svd_preds_df_global.rename(columns={'predicted_rating': 'pred_rating'})
    except ValueError:
        return pd.DataFrame(columns=['movieId', 'title', 'hybrid_score', 'reason'])

    seen = set(ratings_global.loc[ratings_global.userId == userId, 'movieId'].unique())
    candidates = [mid for mid in movie_ids_global if mid not in seen]
    
    log(f"Scoring {len(candidates)} candidate movies for user {userId} (Hybrid)...")
    
    scores = []
    for mid in tqdm(candidates, desc=f"Scoring user {userId} (Hybrid)"):
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
    # นี่คือหน้าแรกสุด (เดี๋ยวเราจะให้ JS มาเรียกแทน)
    return "Welcome to the Recommendation API!"

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
        return jsonify({"error": str(e)}), 400

# (คุณสามารถสร้าง Endpoint สำหรับ Test 1, 2.2, 3 เพิ่มเติมได้ตามต้องการ)
# เช่น @app.route("/api/recommend/movie/<string:movie_title>")

# (ฟังก์ชัน log และ load_svd_artifacts ควรถูกคัดลอกมาที่นี่ด้วย)
def log(msg: str, level: str = "INFO"): print(f"[{level}] {msg}")

# ... (เพิ่มฟังก์ชันอื่นๆ ที่จำเป็น) ...