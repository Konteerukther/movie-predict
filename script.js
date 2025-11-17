// --- ⚠️ แก้ไขตรงนี้เป็น URL ของคุณจาก Render ---
const API_BASE_URL = "https://ชื่อแอปของคุณ.onrender.com"; 
// เช่น "https://movie-recsys-api.onrender.com" (ไม่มี slash ปิดท้าย)

async function getRecommendations() {
    // 1. อ้างอิง Elements ในหน้าเว็บ
    const userIdInput = document.getElementById('userIdInput');
    const resultsArea = document.getElementById('results-area');
    const loading = document.getElementById('loading');
    const errorMsg = document.getElementById('error-msg');
    const btn = document.getElementById('btnRecommend');

    // 2. เคลียร์ค่าเก่า และแสดง Loading
    resultsArea.innerHTML = '';
    errorMsg.classList.add('d-none');
    loading.classList.remove('d-none'); // โชว์ loading
    btn.disabled = true; // ปิดปุ่มห้ามกดรัว

    const userId = userIdInput.value;

    if (!userId) {
        showError("กรุณากรอก User ID ก่อนครับ");
        resetUI();
        return;
    }

    try {
        // 3. ยิง Request ไปหา Backend (Render)
        // เรียกไปที่ Endpoint ที่เราสร้างไว้ใน app.py (เช่น /api/recommend/user/42)
        const response = await fetch(`${API_BASE_URL}/api/recommend/user/${userId}`);

        // 4. ตรวจสอบว่า Backend ตอบกลับมาดีไหม
        if (!response.ok) {
            throw new Error(`Server Error: ${response.status}`);
        }

        const data = await response.json(); // แปลงผลลัพธ์เป็น JSON

        // 5. วนลูปสร้างการ์ดหนัง
        if (data.length === 0) {
            resultsArea.innerHTML = '<div class="col-12 text-center text-muted">ไม่พบข้อมูลหนังแนะนำ</div>';
        } else {
            data.forEach(movie => {
                // สร้าง HTML การ์ดหนังทีละใบ
                const movieCard = `
                    <div class="col-md-6">
                        <div class="card h-100 shadow-sm movie-card">
                            <div class="card-body">
                                <h5 class="card-title text-primary">${movie.title}</h5>
                                <span class="badge bg-success score-badge">
                                    ★ ${parseFloat(movie.hybrid_score || movie.predicted_rating).toFixed(1)}
                                </span>
                                <p class="card-text text-muted small">Movie ID: ${movie.movieId}</p>
                            </div>
                        </div>
                    </div>
                `;
                // เอาการ์ดไปต่อท้ายในกล่อง results
                resultsArea.innerHTML += movieCard;
            });
        }

    } catch (error) {
        console.error(error);
        showError(`เกิดข้อผิดพลาด: ${error.message}. (ลองเช็คว่า Server Render ตื่นหรือยัง)`);
    } finally {
        resetUI();
    }

    // ฟังก์ชันช่วย: คืนค่าปุ่มและปิด Loading
    function resetUI() {
        loading.classList.add('d-none');
        btn.disabled = false;
    }

    // ฟังก์ชันช่วย: แสดง Error
    function showError(msg) {
        errorMsg.textContent = msg;
        errorMsg.classList.remove('d-none');
    }
}