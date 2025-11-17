#!/bin/bash
set -e

echo "--- Start Script Running (Robust Local Version) ---"

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

# 2. Download Data
# สร้างโฟลเดอร์ data รอไว้
mkdir -p data

echo "Downloading files from R2 to ./data ..."
# สั่ง Sync จากถัง R2 ลงมาที่โฟลเดอร์ data ในเครื่อง Render
# (Sync จะดึงทุกไฟล์ในถัง รวมถึง popular_movies.csv ถ้าคุณอัปโหลดขึ้นไปแล้ว)
./rclone sync MyR2:${R2_BUCKET_NAME} data -P --transfers=8

# 3. ตรวจสอบไฟล์ (Debug)
echo "========================================"
echo "🔎 DEBUG: ตรวจสอบไฟล์ใน ./data"
echo "========================================"
ls -R data
echo "========================================"

# 4. Start App
echo "Starting Flask Application..."
# Timeout 300 เพื่อกันเหนียวตอนโหลดโมเดลครั้งแรก
exec gunicorn app:app --timeout 300