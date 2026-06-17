import os
import sys
import subprocess
from pathlib import Path

def build_executable():
    """Build the executable for desktop launching"""
    
    # First, check if we have the needed dependencies
    try:
        import PySide6
        import cx_Freeze
        print("✓ Required dependencies found")
    except ImportError as e:
        print(f"Missing dependency: {e}")
        return False
    
    # Create a build directory
    build_dir = Path("build")
    build_dir.mkdir(exist_ok=True)
    
    # Configuration for cx_Freeze
    executables = [
        "src/crisp/__main__.py"
    ]
    
    print("Creating installation package...")
    
    try:
        # For now, simply create the desktop shortcut since direct executable creation 
        # requires a complex setup environment
        return create_desktop_shortcut()
    except Exception as e:
        print(f"Error in executable build: {e}")
        return False
    
def create_desktop_shortcut():
    """Create a desktop shortcut for launching the application"""
    
    try:
        # Create batch file that will launch the application
        desk_dir = Path(os.path.expanduser("~/Desktop"))
        
        # This is a simplified approach - in practice, we'd need to 
        # set up proper installation paths using pip install etc.
        launcher_script = desk_dir / "AudioCleanUpTool.bat"
        
        script_content = f'''@echo off
cd /d "{Path(os.path.abspath('.')).parent}"
python -m crisp
'''
        
        launcher_script.write_text(script_content)
        print("✓ Desktop shortcut created at:", launcher_script)
        
        return True
    except Exception as e:
        print(f"Error creating desktop shortcut: {e}")
        return False

if __name__ == "__main__":
    build_executable()