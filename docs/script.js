// --- ⚠️ แก้ไขตรงนี้เป็น URL ของคุณจาก Render ---
const API_BASE_URL = "https://movie-predict-624b.onrender.com"; 
// (เช็กให้ชัวร์ว่าลิงก์ถูกต้องและไม่มี slash ปิดท้าย)
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

    // 2. Determine Endpoint & Parameter based on Tab
    try {
        if (type === 'hybrid') {
            const val = document.getElementById('inputHybrid').value;
            if (!val) throw new Error("กรุณากรอก User ID");
            endpoint = `/api/test/hybrid?id=${val}`;
        } 
        else if (type === 'content') {
            // เปลี่ยนไปใช้ค่าจาก movieInput แทน (เพราะเราแก้ HTML แล้ว)
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

// --- 👇 ส่วนที่เพิ่มเข้ามา: Autocomplete Logic 👇 ---
// by Gemini
// const movieInput = document.getElementById('movieInput');
// const suggestionsBox = document.getElementById('suggestions');
// let timeout = null; // สำหรับหน่วงเวลา (Debounce)

// if (movieInput) {
//     // 1. เมื่อมีการพิมพ์
//     movieInput.addEventListener('input', function() {
//         const query = this.value.trim();
        
//         // Clear timeout เดิม (ถ้าพิมพ์รัวๆ ให้รอหยุดพิมพ์ก่อนค่อยหา)
//         clearTimeout(timeout);
        
//         if (query.length < 2) {
//             suggestionsBox.style.display = 'none';
//             return;
//         }

//         // รอ 300ms หลังหยุดพิมพ์ค่อยเรียก API
//         timeout = setTimeout(async () => {
//             try {
//                 // เรียก API ค้นหาชื่อหนัง
//                 const res = await fetch(`${API_BASE_URL}/api/movies/search?q=${encodeURIComponent(query)}`);
//                 const movies = await res.json();
                
//                 if (movies.length > 0) {
//                     showSuggestions(movies);
//                 } else {
//                     suggestionsBox.style.display = 'none';
//                 }
//             } catch (err) {
//                 console.error("Search Error:", err);
//             }
//         }, 300);
//     });

//     // 2. ซ่อน Dropdown เมื่อคลิกที่อื่น
//     document.addEventListener('click', function(e) {
//         if (!movieInput.contains(e.target) && !suggestionsBox.contains(e.target)) {
//             suggestionsBox.style.display = 'none';
//         }
//     });
// }

// // ฟังก์ชันสร้างรายการ Dropdown
// function showSuggestions(movies) {
//     suggestionsBox.innerHTML = ''; // เคลียร์ของเก่า
    
//     movies.forEach(movie => {
//         const div = document.createElement('div');
//         div.className = 'suggestion-item';
//         div.innerHTML = `🎬 ${movie.title}`; 
        
//         // เมื่อคลิกเลือก
//         div.onclick = function() {
//             movieInput.value = movie.title; // ใส่ชื่อหนังลง Input
//             suggestionsBox.style.display = 'none'; // ซ่อน Dropdown
//             // runTest('content'); // (Optional) ถ้าอยากให้กดแล้วค้นหาเลย ให้เอา comment ออก
//         };
        
//         suggestionsBox.appendChild(div);
//     });
    
//     suggestionsBox.style.display = 'block'; // โชว์กล่อง
// }

// by ChatGPT
function setupAutoComplete(inputId) {
    const input = document.getElementById(inputId);
    const box = document.getElementById('suggestions');
    let timeout = null;

    input.addEventListener('input', () => {
        const q = input.value.trim();
        clearTimeout(timeout);

        if (q.length < 2) return (box.style.display = 'none');

        timeout = setTimeout(async () => {
            try {
                const res = await fetch(`${API_BASE_URL}/api/movies/search?q=${encodeURIComponent(q)}`);
                const movies = await res.json();
                movies.length ? showSuggestions(input, box, movies) : (box.style.display = 'none');
            } catch (err) {
                console.error(err);
            }
        }, 300);
    });

    document.addEventListener('click', e => {
        if (!input.contains(e.target) && !box.contains(e.target)) {
            box.style.display = 'none';
        }
    });
}

function showSuggestions(input, box, movies) {
    box.innerHTML = '';
    movies.forEach(m => {
        const div = document.createElement('div');
        div.className = 'suggestion-item';
        div.textContent = `🎬 ${m.title}`;
        div.onclick = () => {
            input.value = m.title;
            box.style.display = 'none';
        };
        box.appendChild(div);
    });
    box.style.display = 'block';
}

// ⭐ เรียกใช้กับ 2 input
setupAutoComplete('movieInput');
setupAutoComplete('inputItemCF');
