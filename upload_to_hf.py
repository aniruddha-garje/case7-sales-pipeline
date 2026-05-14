"""
Upload dashboard/ folder to HF Spaces using huggingface_hub.
Handles LFS automatically — no git-lfs setup needed.

Usage:
    python upload_to_hf.py YOUR_HF_WRITE_TOKEN
"""
import sys
import os
from huggingface_hub import HfApi

TOKEN    = sys.argv[1] if len(sys.argv) > 1 else input("HF Write Token: ")
REPO_ID  = "AniruddhaGarje/case7-sales-dashboard"
SRC_DIR  = os.path.join(os.path.dirname(__file__), "dashboard")

api = HfApi(token=TOKEN)

print(f"Uploading {SRC_DIR} → {REPO_ID} ...")
api.upload_folder(
    folder_path=SRC_DIR,
    repo_id=REPO_ID,
    repo_type="space",
    commit_message="deploy: upload dashboard with pre-built sales.duckdb",
)
print("Done! Check https://huggingface.co/spaces/" + REPO_ID)
