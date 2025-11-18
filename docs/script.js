// --- ⚠️ แก้ไขตรงนี้เป็น URL ของคุณจาก Render ---
const API_BASE_URL = "https://movie-predict-624b.onrender.com"; 

async function runTest(type) {
    // 1. Setup UI
    const resultsArea = document.getElementById('results-area');
    const loading = document.getElementById('loading');
    const errorMsg = document.getElementById('error-msg');
    
    resultsArea.innerHTML = '';
    errorMsg.classList.add('d-none');
    loading.style.display = 'block';

    let endpoint = '';

    // 2. Determine Endpoint & Parameter based on Tab
    try {
        if (type === 'hybrid') {
            const val = document.getElementById('inputHybrid').value;
            if (!val) throw new Error("กรุณากรอก User ID");
            endpoint = `/api/test/hybrid?id=${val}`;
        } 
        else if (type === 'content') {
            // Tab 2 ใช้ movieInput
            const val = document.getElementById('movieInput').value;
            if (!val) throw new Error("กรุณากรอกชื่อหนัง");
            endpoint = `/api/test/content?movie=${encodeURIComponent(val)}`;
        }
        else if (type === 'cf_user') {
            const val = document.getElementById('inputUserCF').value;
            if (!val) throw new Error("กรุณากรอก User ID");
            endpoint = `/api/test/cf_user?id=${val}`;
        }
        else if (type === 'cf_item') {
            // Tab 4 ใช้ itemInput (ตัวใหม่ที่เราเพิ่งสร้าง)
            const val = document.getElementById('itemInput').value;
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
            resultsArea.innerHTML = `
                <div class="col-12 text-center py-5">
                    <h5 class="text-muted">${data.status || "ไม่พบข้อมูลที่ค้นหา หรือหนังนี้ไม่มีในระบบ"}</h5>
                </div>`;
            return;
        }

        data.forEach(item => {
            const title = item.title || `User ID: ${item.userId}`; 
            const sub = item.movieId ? `Movie ID: ${item.movieId}` : `Predicted Rating`;
            
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

// --- 👇 ส่วนที่เพิ่มเข้ามา: Reusable Autocomplete System 👇 ---

// ฟังก์ชันสร้างระบบค้นหาให้ Input ใดๆ ก็ได้
function setupAutocomplete(inputId, suggestionsId) {
    const inputElement = document.getElementById(inputId);
    const suggestionsBox = document.getElementById(suggestionsId);
    let timeout = null;

    if (!inputElement || !suggestionsBox) return; // ถ้าหาไม่เจอให้ข้าม

    // 1. เมื่อพิมพ์
    inputElement.addEventListener('input', function() {
        const query = this.value.trim();
        clearTimeout(timeout);
        
        if (query.length < 2) {
            suggestionsBox.style.display = 'none';
            return;
        }

        timeout = setTimeout(async () => {
            try {
                const res = await fetch(`${API_BASE_URL}/api/movies/search?q=${encodeURIComponent(query)}`);
                const movies = await res.json();
                
                if (movies.length > 0) {
                    // Render Dropdown
                    suggestionsBox.innerHTML = '';
                    movies.forEach(movie => {
                        const div = document.createElement('div');
                        div.className = 'suggestion-item';
                        div.innerHTML = `🎬 ${movie.title}`;
                        div.onclick = function() {
                            inputElement.value = movie.title; // ใส่ค่าลง Input ตัวนั้น
                            suggestionsBox.style.display = 'none';
                        };
                        suggestionsBox.appendChild(div);
                    });
                    suggestionsBox.style.display = 'block';
                } else {
                    suggestionsBox.style.display = 'none';
                }
            } catch (err) {
                console.error("Search Error:", err);
            }
        }, 300);
    });

    // 2. ซ่อนเมื่อคลิกที่อื่น
    document.addEventListener('click', function(e) {
        if (!inputElement.contains(e.target) && !suggestionsBox.contains(e.target)) {
            suggestionsBox.style.display = 'none';
        }
    });
}

// --- เรียกใช้งานระบบค้นหากับทั้ง 2 ช่อง ---
// 1. Tab Content-Based
setupAutocomplete('movieInput', 'suggestions');

// 2. Tab Item CF (ที่เพิ่มมาใหม่)
setupAutocomplete('itemInput', 'itemSuggestions');