# Synth1 to Hive preset converter
Essentially, all you need is one file and run it from the command line. Or two files which makes it easier, and run the batch file.
Download these two files:
- convert_s1_hive.py
- Convert S1-Hive.bat

To convert the script to an exe run this command in cmdprompt:
- "D:\path\to\python.exe" -m PyInstaller --onefile --distpath "D:\path\to\- Build EXE.bat" --workpath "D:\path\to\build" --specpath "D:\path\to\build" "D:\path\to\scripts\convert_s1_hive.py"

Or, just run the "Build EXE.bat" file.

Or you can use the script directly by running the Batch file, you may need to edit the python.exe path within it though:
- Convert S1-Hive.bat

Double click EXE to run, or run from cmd:
cmd /k "D:\path\to\convert_s1_hive.exe"

To convert your Synth1 preset files, just put all your non-zipped banks into the "input" folder, double click the EXE and they will be placed in the "output" folder, keeping the original folder structure.

### NOTE:
For the conversion to work correctly, you MUST update all Synth1 presets to Ver=113! You can use the AutoHotKey script for this, but it can only do so automatically one bank at a time.Synth1-Hive_PresetConverter
