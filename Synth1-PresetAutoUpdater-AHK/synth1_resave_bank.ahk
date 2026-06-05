#Requires AutoHotkey v2.0
#SingleInstance Force

global INI_FILE := A_ScriptDir "\synth1_resave_bank.ini"

global WRITE_X := 0
global WRITE_Y := 0

global SAVE_X := 0
global SAVE_Y := 0

global NEXT_X := 0
global NEXT_Y := 0

global CLICK_DELAY := 250
global SAVE_DELAY := 400
global NEXT_DELAY := 400

global PATCH_COUNT := 128

LoadSettings()
StartupPrompt()

F1::CaptureWrite()
F2::CaptureSave()
F3::CaptureNext()
F4::ResetSavedCoordinates()
F5::RunBatch()
Esc::ExitApp()

LoadSettings() {
    global INI_FILE
    global WRITE_X, WRITE_Y, SAVE_X, SAVE_Y, NEXT_X, NEXT_Y

    if !FileExist(INI_FILE)
        return

    WRITE_X := Integer(IniRead(INI_FILE, "Coords", "WRITE_X", "0"))
    WRITE_Y := Integer(IniRead(INI_FILE, "Coords", "WRITE_Y", "0"))
    SAVE_X  := Integer(IniRead(INI_FILE, "Coords", "SAVE_X",  "0"))
    SAVE_Y  := Integer(IniRead(INI_FILE, "Coords", "SAVE_Y",  "0"))
    NEXT_X  := Integer(IniRead(INI_FILE, "Coords", "NEXT_X",  "0"))
    NEXT_Y  := Integer(IniRead(INI_FILE, "Coords", "NEXT_Y",  "0"))
}

SaveSettings() {
    global INI_FILE
    global WRITE_X, WRITE_Y, SAVE_X, SAVE_Y, NEXT_X, NEXT_Y

    IniWrite WRITE_X, INI_FILE, "Coords", "WRITE_X"
    IniWrite WRITE_Y, INI_FILE, "Coords", "WRITE_Y"
    IniWrite SAVE_X,  INI_FILE, "Coords", "SAVE_X"
    IniWrite SAVE_Y,  INI_FILE, "Coords", "SAVE_Y"
    IniWrite NEXT_X,  INI_FILE, "Coords", "NEXT_X"
    IniWrite NEXT_Y,  INI_FILE, "Coords", "NEXT_Y"
}

HasSavedCoordinates() {
    global WRITE_X, WRITE_Y, SAVE_X, SAVE_Y, NEXT_X, NEXT_Y
    return (WRITE_X != 0 && WRITE_Y != 0
         && SAVE_X  != 0 && SAVE_Y  != 0
         && NEXT_X  != 0 && NEXT_Y  != 0)
}

StartupPrompt() {
    global PATCH_COUNT

    patchCount := PATCH_COUNT

    if HasSavedCoordinates() {
        result := MsgBox(
            "Synth1 Batch Resave is ready.`n`n" .
            "This will process " patchCount " patches.`n`n" .
            "YES = use saved coordinates`n" .
            "NO = recapture coordinates`n" .
            "CANCEL = exit",
            "Synth1 Batch Resave",
            "YesNoCancel"
        )

        if (result = "Yes") {
            return
        } else if (result = "No") {
            MsgBox "Recapture coordinates:`n`nF1 = WRITE`nF2 = SAVE`nF3 = NEXT`n`nThen press F5 to start."
            return
        } else {
            ExitApp
        }
    } else {
        MsgBox "No saved coordinates found.`n`nCapture them now:`n`nF1 = WRITE`nF2 = SAVE`nF3 = NEXT`n`nThen press F5 to start."
    }
}

CaptureWrite() {
    global WRITE_X, WRITE_Y
    MouseGetPos &WRITE_X, &WRITE_Y
    SaveSettings()
    ToolTip "Captured WRITE at " WRITE_X "," WRITE_Y
    SetTimer () => ToolTip(), -1000
}

CaptureSave() {
    global SAVE_X, SAVE_Y
    MouseGetPos &SAVE_X, &SAVE_Y
    SaveSettings()
    ToolTip "Captured SAVE at " SAVE_X "," SAVE_Y
    SetTimer () => ToolTip(), -1000
}

CaptureNext() {
    global NEXT_X, NEXT_Y
    MouseGetPos &NEXT_X, &NEXT_Y
    SaveSettings()
    ToolTip "Captured NEXT at " NEXT_X "," NEXT_Y
    SetTimer () => ToolTip(), -1000
}

ResetSavedCoordinates() {
    global WRITE_X, WRITE_Y, SAVE_X, SAVE_Y, NEXT_X, NEXT_Y, INI_FILE

    WRITE_X := 0
    WRITE_Y := 0
    SAVE_X := 0
    SAVE_Y := 0
    NEXT_X := 0
    NEXT_Y := 0

    if FileExist(INI_FILE)
        FileDelete INI_FILE

    MsgBox "Saved coordinates were reset.`n`nCapture again with:`nF1 = WRITE`nF2 = SAVE`nF3 = NEXT"
}

ClickAt(x, y) {
    MouseMove x, y, 0
    Sleep 100
    Click
}

RunBatch() {
    global WRITE_X, WRITE_Y, SAVE_X, SAVE_Y, NEXT_X, NEXT_Y
    global CLICK_DELAY, SAVE_DELAY, NEXT_DELAY, PATCH_COUNT

    patchCount := PATCH_COUNT

    if !HasSavedCoordinates() {
        MsgBox "Please capture WRITE, SAVE, and NEXT positions first.`n`nF1 = WRITE`nF2 = SAVE`nF3 = NEXT"
        return
    }

    result := MsgBox(
        "Make sure Synth1 is visible and the FIRST patch is selected.`n`n" .
        "This will process " patchCount " patches.`n`n" .
        "Press OK to start.",
        "Start Synth1 Batch Resave?",
        "OKCancel"
    )

    if (result != "OK")
        return

    Loop patchCount {
        ClickAt(WRITE_X, WRITE_Y)
        Sleep CLICK_DELAY

        ClickAt(SAVE_X, SAVE_Y)
        Sleep SAVE_DELAY

        if (A_Index < patchCount) {
            ClickAt(NEXT_X, NEXT_Y)
            Sleep NEXT_DELAY
        }

        ToolTip "Processed patch " A_Index " / " patchCount
    }

    ToolTip "Done."
    SetTimer () => ToolTip(), -1500
    MsgBox "Batch resave complete."
}