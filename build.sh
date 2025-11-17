#!/bin/bash
set -e

echo "--- Build Script Started ---"

# 1. Install dependencies
pip install -r requirements.txt

# 2. Install rclone
curl https://rclone.org/install.sh | bash

# 3. Configure rclone (ใช้ Environment Variables ที่เราจะตั้งใน Render)
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

# 4. Download models from R2 (ถ้ายังไม่มี)
# เปลี่ยน 'my-movie-models-2025' เป็นชื่อ Bucket ของคุณ
if [ ! -d "/var/data/processed" ]; then
  # ใช้ตัวแปร ${R2_BUCKET_NAME} แทนชื่อตายตัว
  echo "Downloading models from bucket: ${R2_BUCKET_NAME}..."
  rclone sync MyR2:${R2_BUCKET_NAME}/processed /var/data/processed -P
else
  echo "Models found. Skipping download."
fi

echo "--- Build Script Finished ---"