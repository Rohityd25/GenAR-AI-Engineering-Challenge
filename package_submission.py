"""
Packaging script for GenAR Pharmacovigilance Engineering Challenge submission.
Creates a clean submission zip archive adhering strictly to the Submission Guide.
"""

import os
import zipfile
from pathlib import Path


def create_submission_zip(output_zip_name: str = "rohit_yadav_genar_challenge.zip"):
    root_dir = Path(".")
    zip_path = Path(output_zip_name)

    # Exclusions per Submission Guide
    excluded_dirs = {
        "__pycache__", ".pytest_cache", ".git", "venv", ".env", "node_modules", ".vscode", ".idea"
    }
    excluded_extensions = {".pyc", ".pyo", ".xlsx", ".csv", ".tsv", ".zip", ".log"}

    print(f"Creating submission zip: {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for folder_name, subfolders, filenames in os.walk(root_dir):
            # Prune excluded directories
            subfolders[:] = [d for d in subfolders if d not in excluded_dirs]
            
            for filename in filenames:
                file_path = Path(folder_name) / filename
                rel_path = file_path.relative_to(root_dir)

                # Skip excluded files
                if file_path.suffix.lower() in excluded_extensions:
                    continue
                if any(part in excluded_dirs for part in file_path.parts):
                    continue
                if filename.startswith(".") and filename != ".gitignore":
                    continue

                print(f"  Adding: {rel_path}")
                zip_file.write(file_path, arcname=str(rel_path))

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Done! Submission archive created: {zip_path} (Size: {size_mb:.2f} MB)")


if __name__ == "__main__":
    create_submission_zip()
