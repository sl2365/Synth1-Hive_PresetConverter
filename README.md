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



# Synth1 Bank/Preset Updater:

## First-time setup
Open "- RUN_synth1_resave_bank.bat" and edit the path to AutoHotkey64.exe

### How to use it...
### Step 1
Launch = RUN_synth1_resave_bank.bat
This starts the AHK script.

### Step 2
Open Synth1 and make sure:
- the window is visible
- the bank is loaded manually
- patch 1 is selected manually

### Step 3
Capture the three button positions:
- Press F1 while hovering mouse over write,
- Press F2 while hovering mouse over Save,
- Press F3 while hovering mouse over next patch,
Each one should show a tiny tooltip saying it captured the position.

## What to expect while using it:
When you press F5:
- A confirmation box appears
- after you press OK, the mouse will move by itself
- it will click:
    write
    save
    next
- it will repeat for 128 patches
- a small tooltip will show progress like:
	Processed patch 1 / 128
	Processed patch 2 / 128
- then it shows:
	Batch resave complete.

## Important while it is running:
; Do not:
- move the Synth1 window
- click the mouse
- type on keyboard
- switch to another window

Just let it finish.

## How to stop it:
Press [Esc]

That exits the script.
Use that if something goes wrong.

