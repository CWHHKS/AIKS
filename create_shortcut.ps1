$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'AIKA Research Tool.lnk')
$Shortcut = $WshShell.CreateShortcut($DesktopPath)
$Shortcut.TargetPath = 'c:\AGIChang\AIKA\AI Vendors Find\run_app.bat'
$Shortcut.WorkingDirectory = 'c:\AGIChang\AIKA\AI Vendors Find'
$Shortcut.IconLocation = 'imageres.dll,80'
$Shortcut.Save()
Write-Host "Shortcut created successfully at: $DesktopPath"
