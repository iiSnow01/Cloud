Option Explicit

Dim shell, fso, root, pythonw, mainFile, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = root & "\.venv\Scripts\python.exe"
mainFile = root & "\main.py"

If Not fso.FileExists(pythonw) Then
    MsgBox "Missing launcher: " & pythonw, vbCritical, "Cloudgram"
    WScript.Quit 1
End If

If Not fso.FileExists(mainFile) Then
    MsgBox "Missing file: " & mainFile, vbCritical, "Cloudgram"
    WScript.Quit 1
End If

command = "cmd /c cd /d """ & root & """ && set CLOUDGRAM_GUI_BOOTSTRAP=1 && """ & pythonw & """ """ & mainFile & """"
shell.Run command, 0, False
