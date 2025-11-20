#!/usr/bin/env python3
"""
System Cleanup Script
Removes temporary files, cache directories, and cleans up the repository
"""

import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def cleanup():
    """Perform system cleanup"""
    print("=" * 70)
    print("🧹 SYSTEM CLEANUP")
    print("=" * 70)
    print()
    
    total_size = 0
    cleaned_items = []
    
    # 1. Remove __pycache__ directories
    print("1. Cleaning __pycache__ directories...")
    pycache_dirs = list(PROJECT_ROOT.rglob("__pycache__"))
    for pycache_dir in pycache_dirs:
        try:
            size = sum(f.stat().st_size for f in pycache_dir.rglob("*") if f.is_file())
            shutil.rmtree(pycache_dir)
            total_size += size
            cleaned_items.append(f"Removed: {pycache_dir.relative_to(PROJECT_ROOT)} ({size / 1024:.2f} KB)")
            print(f"   ✅ Removed: {pycache_dir.relative_to(PROJECT_ROOT)}")
        except Exception as e:
            print(f"   ⚠️  Error removing {pycache_dir}: {e}")
    print(f"   Cleaned {len(pycache_dirs)} __pycache__ directories")
    print()
    
    # 2. Remove .pyc files
    print("2. Cleaning .pyc files...")
    pyc_files = list(PROJECT_ROOT.rglob("*.pyc"))
    for pyc_file in pyc_files:
        try:
            size = pyc_file.stat().st_size
            pyc_file.unlink()
            total_size += size
            cleaned_items.append(f"Removed: {pyc_file.relative_to(PROJECT_ROOT)} ({size / 1024:.2f} KB)")
        except Exception as e:
            print(f"   ⚠️  Error removing {pyc_file}: {e}")
    print(f"   Cleaned {len(pyc_files)} .pyc files")
    print()
    
    # 3. Remove .pyo files
    print("3. Cleaning .pyo files...")
    pyo_files = list(PROJECT_ROOT.rglob("*.pyo"))
    for pyo_file in pyo_files:
        try:
            size = pyo_file.stat().st_size
            pyo_file.unlink()
            total_size += size
            cleaned_items.append(f"Removed: {pyo_file.relative_to(PROJECT_ROOT)}")
        except Exception as e:
            print(f"   ⚠️  Error removing {pyo_file}: {e}")
    print(f"   Cleaned {len(pyo_files)} .pyo files")
    print()
    
    # 4. Remove .DS_Store files (macOS)
    print("4. Cleaning .DS_Store files...")
    ds_store_files = list(PROJECT_ROOT.rglob(".DS_Store"))
    for ds_file in ds_store_files:
        try:
            ds_file.unlink()
            cleaned_items.append(f"Removed: {ds_file.relative_to(PROJECT_ROOT)}")
        except Exception as e:
            print(f"   ⚠️  Error removing {ds_file}: {e}")
    print(f"   Cleaned {len(ds_store_files)} .DS_Store files")
    print()
    
    # 5. Remove cache directories
    print("5. Cleaning cache directories...")
    cache_dirs = [
        PROJECT_ROOT / ".pytest_cache",
        PROJECT_ROOT / ".mypy_cache",
        PROJECT_ROOT / ".ruff_cache",
        PROJECT_ROOT / ".coverage",
        PROJECT_ROOT / "htmlcov",
        PROJECT_ROOT / ".tox",
    ]
    for cache_dir in cache_dirs:
        if cache_dir.exists():
            try:
                size = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file())
                shutil.rmtree(cache_dir)
                total_size += size
                cleaned_items.append(f"Removed: {cache_dir.name} ({size / 1024:.2f} KB)")
                print(f"   ✅ Removed: {cache_dir.name}")
            except Exception as e:
                print(f"   ⚠️  Error removing {cache_dir}: {e}")
    print()
    
    # 6. Archive old log files (keep last 10)
    print("6. Archiving old log files...")
    logs_dir = PROJECT_ROOT / "logs"
    if logs_dir.exists():
        log_files = sorted(logs_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
        if len(log_files) > 10:
            old_logs = log_files[10:]
            for log_file in old_logs:
                try:
                    size = log_file.stat().st_size
                    log_file.unlink()
                    total_size += size
                    cleaned_items.append(f"Removed old log: {log_file.name} ({size / 1024:.2f} KB)")
                    print(f"   ✅ Removed old log: {log_file.name}")
                except Exception as e:
                    print(f"   ⚠️  Error removing {log_file}: {e}")
            print(f"   Kept {len(log_files) - len(old_logs)} recent log files")
        else:
            print(f"   ✅ All {len(log_files)} log files kept (within limit)")
    print()
    
    # 7. Remove temporary files
    print("7. Cleaning temporary files...")
    temp_patterns = ["*.tmp", "*.temp", "*~", "*.swp", "*.swo"]
    temp_files = []
    for pattern in temp_patterns:
        temp_files.extend(PROJECT_ROOT.rglob(pattern))
    
    for temp_file in temp_files:
        try:
            size = temp_file.stat().st_size
            temp_file.unlink()
            total_size += size
            cleaned_items.append(f"Removed: {temp_file.relative_to(PROJECT_ROOT)}")
        except Exception as e:
            print(f"   ⚠️  Error removing {temp_file}: {e}")
    print(f"   Cleaned {len(temp_files)} temporary files")
    print()
    
    # 8. Remove .ipynb_checkpoints
    print("8. Cleaning Jupyter checkpoints...")
    checkpoint_dirs = list(PROJECT_ROOT.rglob(".ipynb_checkpoints"))
    for checkpoint_dir in checkpoint_dirs:
        try:
            size = sum(f.stat().st_size for f in checkpoint_dir.rglob("*") if f.is_file())
            shutil.rmtree(checkpoint_dir)
            total_size += size
            cleaned_items.append(f"Removed: {checkpoint_dir.relative_to(PROJECT_ROOT)}")
            print(f"   ✅ Removed: {checkpoint_dir.relative_to(PROJECT_ROOT)}")
        except Exception as e:
            print(f"   ⚠️  Error removing {checkpoint_dir}: {e}")
    print(f"   Cleaned {len(checkpoint_dirs)} checkpoint directories")
    print()
    
    # Summary
    print("=" * 70)
    print("✅ CLEANUP COMPLETE")
    print("=" * 70)
    print(f"Total space freed: {total_size / (1024 * 1024):.2f} MB")
    print(f"Total items cleaned: {len(cleaned_items)}")
    print()
    print("Cleanup complete! Repository is now clean.")


if __name__ == "__main__":
    try:
        cleanup()
    except KeyboardInterrupt:
        print("\n\n⚠️  Cleanup interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()

