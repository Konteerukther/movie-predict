#!/bin/bash
set -e

echo "--- Start Script Running (Runtime Phase) ---"

# 1. Configure rclone (ทำตอนรัน มั่นใจกว่า)
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

# 2. Download Data (ทำตรงนี้ เพราะ Disk ถูก Mount แล้ว!)
# ไม่ต้อง mkdir /var/data เพราะ Render Mount ให้เองแล้ว
if [ ! -d "/var/data/processed/cleaned" ]; then
    echo "Disk is empty. Downloading models from R2..."
    ./rclone sync MyR2:${R2_BUCKET_NAME} /var/data/processed -P --transfers=8
    echo "Download complete."
else
    echo "Data found on Persistent Disk. Skipping download."
fi

# 3. Start App (เริ่ม Flask)
echo "Starting Flask Application..."
exec gunicorn app:app --timeout 300