#!/bin/bash
set -e

echo "--- Build Script Started ---"

# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install rclone (Manual Install to avoid Read-only error)
echo "Downloading rclone..."
curl -O https://downloads.rclone.org/rclone-current-linux-amd64.zip
unzip -o rclone-current-linux-amd64.zip
cd rclone-*-linux-amd64

# ย้ายไฟล์ rclone มาไว้ที่โฟลเดอร์หลักของโปรเจกต์
cp rclone ../rclone
cd ..

# ลบไฟล์ขยะทิ้ง
rm -rf rclone-*-linux-amd64 rclone-current-linux-amd64.zip

# ทำให้ rclone รันได้
chmod +x rclone
echo "rclone installed successfully to $(pwd)/rclone"

# 3. Configure rclone
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

# 4. Download models using local rclone
# (ใช้ ./rclone แทน rclone เฉยๆ เพราะไฟล์อยู่ที่นี่ ไม่ใช่ใน /usr/bin)
if [ ! -d "/var/data/processed" ]; then
  echo "Downloading models from bucket: ${R2_BUCKET_NAME}..."
  ./rclone sync MyR2:${R2_BUCKET_NAME}/processed /var/data/processed -P
else
  echo "Models found. Skipping download."
fi

echo "--- Build Script Finished ---"