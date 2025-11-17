#!/bin/bash
set -e

echo "--- Start Script Running (Debug Mode) ---"

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

# 2. Force Download (ไม่มี if-else เพื่อบังคับโหลด)
echo "Force downloading from R2 to /var/data/processed..."

# สร้างโฟลเดอร์ปลายทางรอไว้ก่อน (กันเหนียว)
mkdir -p /var/data/processed

# สั่งโหลดจาก R2 ลงไปที่ /var/data/processed
# (สมมติว่าในถัง R2 คุณมีโฟลเดอร์ 'cleaned' และ 'models' อยู่หน้าแรก)
./rclone sync MyR2:${R2_BUCKET_NAME} /var/data/processed -P --transfers=8

# 3. ⚠️ จุดสำคัญ: ปริ้นท์ไฟล์ให้ดู (Debug Listing)
echo "========================================"
echo "🔎 DEBUG: ดูโครงสร้างไฟล์ใน /var/data"
echo "========================================"
ls -R /var/data
echo "========================================"

# 4. Start App
echo "Starting Flask..."
exec gunicorn app:app --timeout 300