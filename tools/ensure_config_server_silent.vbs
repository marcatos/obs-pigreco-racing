' Silent launcher for tools/ensure_config_server.py (no console window).
' Used by OBS Lua autostart and optional Windows Startup shortcut.
Option Explicit

Dim fso, sh, root, ensure, py, candidates, i, envPy
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")

root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
ensure = root & "\tools\ensure_config_server.py"
If Not fso.FileExists(ensure) Then
  WScript.Quit 2
End If

envPy = ""
On Error Resume Next
envPy = sh.ExpandEnvironmentStrings("%PIGRECO_PYTHON%")
On Error GoTo 0

py = ""
If envPy <> "" And envPy <> "%PIGRECO_PYTHON%" And fso.FileExists(envPy) Then
  ' Prefer pythonw sibling when a console python.exe was configured
  If LCase(Right(envPy, 10)) = "python.exe" Then
    Dim sibling
    sibling = Left(envPy, Len(envPy) - 10) & "pythonw.exe"
    If fso.FileExists(sibling) Then
      py = sibling
    Else
      py = envPy
    End If
  Else
    py = envPy
  End If
End If

If py = "" Then
  candidates = Array( _
    "C:\Python314\pythonw.exe", _
    "C:\Python313\pythonw.exe", _
    "C:\Python312\pythonw.exe", _
    "C:\Python311\pythonw.exe", _
    "C:\Python310\pythonw.exe", _
    "C:\Python314\python.exe", _
    "C:\Python312\python.exe" _
  )
  For i = 0 To UBound(candidates)
    If fso.FileExists(candidates(i)) Then
      py = candidates(i)
      Exit For
    End If
  Next
End If

If py = "" Then
  WScript.Quit 3
End If

' 0 = hidden window, True = wait until ensure exits
sh.Run """" & py & """ """ & ensure & """", 0, True
WScript.Quit 0
