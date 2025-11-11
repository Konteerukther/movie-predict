# Movie Recommendation System - Deployment Demo

> 🚀 This README focuses **only** on the `Deployment.ipynb` file, which serves as an interactive environment for testing, demonstration, and retraining the recommendation models.

## 📄 File Description

`Deployment.ipynb` (Jupyter Notebook) เป็นไฟล์หลักสำหรับ:
1.  **โหลด (Load)** โมเดลที่เทรนเสร็จแล้ว (SVD-CF และ Content-Based)
2.  **ทดสอบ (Test)** โมเดลแต่ละประเภทแบบแยกส่วน
3.  **รับ Feedback (Input)** จากผู้ใช้ผ่าน UI
4.  **เทรนใหม่ (Retrain)** โมเดล SVD (CF) โดยใช้ Feedback ใหม่

ไฟล์นี้ไม่ได้สร้างโมเดล Content-Based (`.npz`) หรือ TF-IDF ใหม่ แต่จะใช้ไฟล์ที่เทรนไว้แล้วจาก `processed/models/` และ `processed/preprocess/` เท่านั้น

---

## 🏛️ Required File Structure

เพื่อให้ Notebook นี้ทำงานได้ (เนื่องจากใช้ Path แบบ Portable) คุณต้องจัดเรียงไฟล์ตามโครงสร้างนี้ โดยวาง `Deployment.ipynb` ไว้ที่ Root:

```
Your_Project_Folder/
├── 🚀 Deployment.ipynb
│
└── processed/
    ├── cleaned/
    │   ├── movies_cleaned_f.csv
    │   └── ratings_cleaned_f.csv
    │
    ├── models/
    │   ├── content_similarity_sparse.npz
    │   ├── svd_U.npy
    │   ├── svd_Sigma.npy
    │   ├── svd_Vt.npy
    │   ├── svd_user_mean.npy
    │   ├── svd_user_index.pkl
    │   ├── svd_movie_index.pkl
    │   ├── svd_reverse_user_index.pkl
    │   └── svd_reverse_movie_index.pkl
    │
    ├── preprocess/
    │   └── movies_tfidf_reduced.csv
    │
    └── user_feedback.csv  <-- (ไฟล์นี้จะถูกสร้างขึ้นอัตโนมัติ)
```

---

## 💡 Key Features & How to Use

คุณต้องรัน Cell ใน Notebook นี้ตามลำดับ

#### 1. (Cell 1-4) Initialization
* **Cell 1:** Imports (ต้องติดตั้ง `ipywidgets`, `pandas`, `scipy`, `numpy`)
* **Cell 2:**
