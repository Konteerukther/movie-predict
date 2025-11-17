#!/bin/bash
set -e

echo "--- Start Script Running (Local Data Version) ---"

# 1. Config rclone
mkdir -p ~/.config/rclone
cat <<EOF > ~/.config/rclone/rclone.conf
[MyR2]
type = s3
provider = Cloudflare
env_auth = false
access_key_id = ${R2_ACCESS_KEY_ID}
secret_access_key = ${R2_SECRET_ACCESS_KEY}
endpoint = https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com
EOF

# 2. Download Data (เปลี่ยนมาลงที่โฟลเดอร์ 'data' ในโปรเจกต์แทน)
echo "Downloading from R2 to ./data ..."

# สร้างโฟลเดอร์ปลายทาง (ในบ้านเราเอง สร้างได้แน่นอน)
mkdir -p data

# สั่งโหลด (ใช้ ./data แทน /var/data)
# หมายเหตุ: ถ้าไม่มี Disk เราต้องโหลดใหม่ทุกครั้งที่ Restart (ยอมแลก)
./rclone sync MyR2:${R2_BUCKET_NAME} data -P --transfers=8

# 3. ตรวจสอบไฟล์ (Debug)
echo "========================================"
echo "🔎 DEBUG: รายชื่อไฟล์ใน ./data"
echo "========================================"
ls -R data
echo "========================================"

# 4. Start App
echo "Starting Flask..."
exec gunicorn app:app --timeout 300