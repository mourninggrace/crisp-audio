import sys
sys.path.insert(0, 'C:\\AudioCleanUpTool')

# Simple test to see if we have basic imports
try:
    from crisp.core.engine import CleanupSettings
    print("✓ CleanupSettings import successful")
    
    from crisp.core.presets import ExportSettings
    print("✓ ExportSettings import successful")
    
    from crisp.core.batch import process_folder
    print("✓ process_folder import successful")
    
    print("All core modules imported successfully - this means we have the basic structure right.")
except ImportError as e:
    print(f"Import error: {e}")
    