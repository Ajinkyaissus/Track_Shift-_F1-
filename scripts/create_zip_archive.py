"""
TrackShift Codebase Zip Archive Generator.

Packages the entire project into a clean zip archive, excluding
git internals, node_modules, pycache, temporary build files, and existing archives.
"""

import os
import zipfile
import sys

EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".idea",
    ".vscode",
    ".tempmediaStorage"
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".zip"
}

EXCLUDE_FILES = {
    "fastf1_http_cache.sqlite",
    "car_data.ff1pkl",
    "position_data.ff1pkl"
}


def create_archive(source_dir: str, output_zip_path: str):
    print(f"Creating codebase zip archive from: {source_dir}")
    print(f"Destination: {output_zip_path}")

    total_files = 0
    total_uncompressed_bytes = 0

    with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=3) as zipf:
        for root, dirs, files in os.walk(source_dir):
            # Prune excluded directories in-place
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for file in files:
                if file in EXCLUDE_FILES:
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext in EXCLUDE_EXTENSIONS:
                    continue

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, source_dir)

                # Ensure we don't zip the output archive itself if created inside source_dir
                if os.path.abspath(full_path) == os.path.abspath(output_zip_path):
                    continue

                zipf.write(full_path, arcname=rel_path)
                total_files += 1
                total_uncompressed_bytes += os.path.getsize(full_path)

    zip_size_mb = os.path.getsize(output_zip_path) / (1024 * 1024)
    raw_size_mb = total_uncompressed_bytes / (1024 * 1024)

    print("==================================================")
    print(" TRACKSHIFT CODEBASE ARCHIVE CREATED")
    print(f" Files Packed:     {total_files:,}")
    print(f" Raw Data Size:    {raw_size_mb:.2f} MB")
    print(f" Compressed Size:  {zip_size_mb:.2f} MB")
    print(f" Archive Location: {output_zip_path}")
    print("==================================================")
    return output_zip_path


if __name__ == "__main__":
    workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    out_dir = os.path.dirname(workspace_dir) # c:\Users\harsh\Downloads
    zip_filename = "TrackShift-codebase-updated.zip"
    dest_path = os.path.join(out_dir, zip_filename)

    # Also place a copy directly in the workspace root for convenience
    dest_workspace_path = os.path.join(workspace_dir, "TrackShift-codebase-updated.zip")

    create_archive(workspace_dir, dest_path)

    # Copy to workspace root
    import shutil
    shutil.copy2(dest_path, dest_workspace_path)
    print(f" Convenience copy placed at: {dest_workspace_path}")
