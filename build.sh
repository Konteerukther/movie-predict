#!/bin/bash
set -e

echo "--- Build Script Started (Robust Version) ---"

# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install rclone (Manual Install)
if [ ! -f "./rclone" ]; then
    echo "Downloading rclone..."
    curl -O https://downloads.rclone.org/rclone-current-linux-amd64.zip
    unzip -o rclone-current-linux-amd64.zip
    cd rclone-*-linux-amd64
    cp rclone ../rclone
    cd ..
    rm -rf rclone-*-linux-amd64 rclone-current-linux-amd64.zip
    chmod +x rclone
    echo "rclone installed successfully."
else
    echo "rclone already exists. Skipping download."
fi

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

# --- ส่วนป้องกัน (Defense Logic) ---

# 4.1 สร้างโฟลเดอร์ปลายทางรอไว้เลย (กันเหนียว error: No such file)
echo "Ensuring destination directory exists..."
mkdir -p /var/data/processed

# 4.2 เช็กของในถัง R2 ก่อน (Debug)
echo "--- DEBUG: Listing files in R2 Bucket: ${R2_BUCKET_NAME} ---"
./rclone lsf MyR2:${R2_BUCKET_NAME} || echo "Warning: Could not list bucket contents. Check credentials or bucket name."
echo "-----------------------------------------------------------"

# 5. Download models
# (ใช้เงื่อนไขเช็กว่ามีโฟลเดอร์ cleaned หรือยัง เพื่อจะได้ไม่โหลดซ้ำถ้ามีแล้ว)
if [ ! -d "/var/data/processed/cleaned" ]; then
  echo "Downloading models from bucket: ${R2_BUCKET_NAME}..."
  
  # Sync จาก R2 ลงมาที่ /var/data/processed
  ./rclone sync MyR2:${R2_BUCKET_NAME} /var/data/processed -P --transfers=4
  
  echo "Sync completed."
else
  echo "Data found on disk (/var/data/processed/cleaned exists). Skipping download."
fi

# 6. ตรวจสอบผลลัพธ์ (Listing)
echo "--- Final Check: Content of /var/data/processed ---"
ls -R /var/data/processed || echo "Directory is empty or not accessible."
echo "--------------------------------------------------"

echo "--- Build Script Finished ---"