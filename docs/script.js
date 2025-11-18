// --- ⚠️ แก้ไขตรงนี้เป็น URL ของคุณจาก Render ---
const API_BASE_URL = "https://movie-predict-624b.onrender.com";
// เช่น "https://movie-recsys-api.onrender.com" (ไม่มี slash ปิดท้าย)

// // แก้จาก URL ของ Render เป็น Localhost
// const API_BASE_URL = "http://127.0.0.1:5000";

async function runTest(type) {
    // 1. Setup UI
    const resultsArea = document.getElementById('results-area');
    const loading = document.getElementById('loading');
    const errorMsg = document.getElementById('error-msg');
    
    resultsArea.innerHTML = '';
    errorMsg.classList.add('d-none');
    loading.style.display = 'block';

    let endpoint = '';
    let param = '';

    // 2. Determine Endpoint & Parameter based on Tab
    try {
        if (type === 'hybrid') {
            const val = document.getElementById('inputHybrid').value;
            if (!val) throw new Error("กรุณากรอก User ID");
            endpoint = `/api/test/hybrid?id=${val}`; // ใช้ Route ใหม่ที่เตรียมไว้
        } 
        else if (type === 'content') {
            const val = document.getElementById('inputContent').value;
            if (!val) throw new Error("กรุณากรอกชื่อหนัง");
            endpoint = `/api/test/content?movie=${encodeURIComponent(val)}`;
        }
        else if (type === 'cf_user') {
            const val = document.getElementById('inputUserCF').value;
            if (!val) throw new Error("กรุณากรอก User ID");
            endpoint = `/api/test/cf_user?id=${val}`;
        }
        else if (type === 'cf_item') {
            const val = document.getElementById('inputItemCF').value;
            if (!val) throw new Error("กรุณากรอกชื่อหนัง");
            endpoint = `/api/test/cf_item?movie=${encodeURIComponent(val)}`;
        }

        // 3. Call API
        console.log(`Calling: ${API_BASE_URL}${endpoint}`);
        const response = await fetch(`${API_BASE_URL}${endpoint}`);
        
        if (!response.ok) {
            const errJson = await response.json();
            throw new Error(errJson.error || `Server Error (${response.status})`);
        }

        const data = await response.json();

        // 4. Render Results
        loading.style.display = 'none';
        
        if (data.length === 0 || data.status) { 
            // กรณีไม่เจอข้อมูล หรือเป็นข้อความ Status
            resultsArea.innerHTML = `
                <div class="col-12 text-center py-5">
                    <h5 class="text-muted">${data.status || "ไม่พบข้อมูลที่ค้นหา หรือหนังนี้ไม่มีในระบบ"}</h5>
                </div>`;
            return;
        }

        data.forEach(item => {
            // เช็คว่าเป็นการแนะนำหนัง หรือแนะนำ User (สำหรับ Tab 4)
            const title = item.title || `User ID: ${item.userId}`; 
            const sub = item.movieId ? `Movie ID: ${item.movieId}` : `Predicted Rating`;
            
            // หาคะแนนที่จะโชว์ (รองรับหลายชื่อตัวแปร)
            let score = item.hybrid_score || item.predicted_rating || item.similarity_score || 0;
            let scoreColor = 'bg-primary';
            if (type === 'hybrid') scoreColor = 'bg-success';
            if (type === 'content') scoreColor = 'bg-info text-dark';
            if (type === 'cf_user') scoreColor = 'bg-warning text-dark';
            if (type === 'cf_item') scoreColor = 'bg-danger';

            const cardHTML = `
                <div class="col-md-6 col-lg-4">
                    <div class="card h-100 shadow-sm movie-card">
                        <div class="card-body">
                            <h5 class="card-title text-dark fw-bold text-truncate">${title}</h5>
                            <span class="badge ${scoreColor} score-badge">
                                Score: ${parseFloat(score).toFixed(2)}
                            </span>
                            <p class="card-text text-muted small mb-0">${sub}</p>
                        </div>
                    </div>
                </div>
            `;
            resultsArea.innerHTML += cardHTML;
        });

    } catch (error) {
        loading.style.display = 'none';
        errorMsg.textContent = `เกิดข้อผิดพลาด: ${error.message}`;
        errorMsg.classList.remove('d-none');
    }
}