<#
modify_resolution.ps1
Safe helper to backup a registry key and update a Resolution-like value to "WIDTH * HEIGHT" or a custom string.
- Preserves the original registry value kind when possible (REG_BINARY/REG_SZ/REG_DWORD/etc).
- Backs up the whole key with `reg export` before modifying.
- Offers a `-Restore` switch to import the backup.

Usage examples:
# Backup & set to 1920 x 1080
pwsh .\modify_resolution.ps1 -KeyPath 'HKCU:\Software\bluepoch' -ValueName 'ResolutionRatio_h997442698' -Width 1920 -Height 1080 -BackupFile '.\\bluepoch_backup.reg'

# Set to a custom string
pwsh .\modify_resolution.ps1 -KeyPath 'HKCU:\Software\bluepoch' -ValueName 'ResolutionRatio_h997442698' -NewValue '1280 * 720'

# Restore from backup
pwsh .\modify_resolution.ps1 -KeyPath 'HKCU:\Software\bluepoch' -BackupFile '.\\bluepoch_backup.reg' -Restore
#>

param(
    [string]$KeyPath = 'HKCU:\Software\bluepoch\Reverse: 1999',
    [string]$ValueName = 'ResolutionRatio_h997442698',
    [ValidateSet('1','2','3','4')]
    [string]$Preset,
    [int]$Width,
    [int]$Height,
    [string]$NewValue,
    [string]$BackupFile = '.\bluepoch_registry_backup.reg',
    [switch]$Restore,
    [switch]$Force
)

function Write-ErrAndExit($msg) {
    Write-Error $msg
    exit 1
}

# Normalize KeyPath
if ($KeyPath -notmatch '^(HKCU|HKLM|HKCR|HKU|HKCC):\\') {
    Write-ErrAndExit "KeyPath must start with one of HKCU:/HKLM:/HKCR:/HKU:/HKCC:. Example: 'HKCU:\\Software\\bluepoch'"
}

if ($Restore) {
    if (-not (Test-Path $BackupFile)) {
        Write-ErrAndExit "Backup file '$BackupFile' not found."
    }

    Write-Host "Importing backup from: $BackupFile"
    $imp = Start-Process -FilePath reg -ArgumentList "import `"$BackupFile`"" -NoNewWindow -Wait -PassThru
    if ($imp.ExitCode -ne 0) {
        Write-ErrAndExit "reg import failed (exit code $($imp.ExitCode))."
    }
    Write-Host "Restore completed."
    exit 0
}

# Determine desired value string
# If no parameters provided, run an interactive main menu
if ($PSBoundParameters.Count -eq 0 -and -not $Restore) {
    while ($true) {
        Write-Host "Select an action:"
        Write-Host "1) Set resolution from preset"
        Write-Host "2) Restore from backup (import .reg)"
        Write-Host "3) Exit"
        $action = Read-Host "Enter choice (1-3)"
        switch ($action) {
            '1' {
                Write-Host "Presets:"
                Write-Host "  a) 1920 * 1080"
                Write-Host "  b) 1600 * 900"
                Write-Host "  c) 1366 * 768"
                Write-Host "  d) 1280 * 720"
                $p = Read-Host "Choose preset (a-d) or 'c' to cancel"
                switch ($p) {
                    'a' { $Width = 1920; $Height = 1080 }
                    'b' { $Width = 1600; $Height = 900 }
                    'c' { $Width = 1366; $Height = 768 }
                    'd' { $Width = 1280; $Height = 720 }
                    default { Write-Host "Cancelled preset selection."; continue }
                }
                $valueToSet = "{0} * {1}" -f $Width, $Height
                break
            }
            '2' {
                # Restore flow
                $bk = Read-Host "Enter backup .reg path to import (or press Enter to use default $BackupFile)"
                if ($bk -ne '') { $BackupFile = $bk }
                if (-not (Test-Path $BackupFile)) { Write-Host "Backup file not found: $BackupFile"; continue }
                Write-Host "Importing backup from: $BackupFile"
                Start-Process -FilePath reg -ArgumentList "import `"$BackupFile`"" -NoNewWindow -Wait
                Write-Host "Restore completed."; exit 0
            }
            '3' { Write-Host "Exit."; exit 0 }
            default { Write-Host "Invalid choice."; continue }
        }
        # break outer loop if a valueToSet was prepared
        if ($null -ne $valueToSet) { break }
    }
} else {
    if ($PSBoundParameters.ContainsKey('NewValue')) {
        $valueToSet = $NewValue
    } elseif ($PSBoundParameters.ContainsKey('Width') -and $PSBoundParameters.ContainsKey('Height')) {
        $valueToSet = "{0} * {1}" -f $Width, $Height
    } elseif ($PSBoundParameters.ContainsKey('Preset')) {
        switch ($Preset) {
            '1' { $Width = 1920; $Height = 1080 }
            '2' { $Width = 1600; $Height = 900 }
            '3' { $Width = 1366; $Height = 768 }
            '4' { $Width = 1280; $Height = 720 }
        }
        $valueToSet = "{0} * {1}" -f $Width, $Height
    } else {
        Write-ErrAndExit "Either supply -NewValue or both -Width and -Height (or run interactively without parameters)."
    }
}

# Confirm
if (-not $Force) {
    Write-Host "About to modify registry key: $KeyPath, value: $ValueName"
    Write-Host "New value: $valueToSet"
    $ok = Read-Host "Proceed? (y/N)"
    if ($ok.ToLower() -ne 'y') { Write-Host "Aborted."; exit 0 }
}

# Export backup
Write-Host "Exporting registry key to: $BackupFile"
$exportTarget = $KeyPath

# Convert PowerShell provider path (HKCU:\...) to reg.exe path (HKCU\...)
function Convert-ToRegKey([string]$psKey) {
    if ($psKey -match '^(HKCU|HKLM|HKCR|HKU|HKCC):\\(.+)$') {
        return "$($matches[1])\$($matches[2])"
    }
    return $psKey
}

$regExportTarget = Convert-ToRegKey $exportTarget
$export = Start-Process -FilePath reg -ArgumentList "export `"$regExportTarget`" `"$BackupFile`" /y" -NoNewWindow -Wait -PassThru
if ($export.ExitCode -ne 0) {
    Write-Host "reg export failed for key '$exportTarget' (exit code $($export.ExitCode)). Trying parent key export..."
    # Try exporting parent key if child key name contains characters unsupported by reg.exe (eg. colon)
    try {
        $lastSlash = $KeyPath.LastIndexOf('\')
        if ($lastSlash -gt 0) {
            $parentKey = $KeyPath.Substring(0, $lastSlash)
            Write-Host "Attempting to export parent key: $parentKey"
            $regParent = Convert-ToRegKey $parentKey
            $export = Start-Process -FilePath reg -ArgumentList "export `"$regParent`" `"$BackupFile`" /y" -NoNewWindow -Wait -PassThru
            if ($export.ExitCode -ne 0) {
                Write-ErrAndExit "reg export failed for parent key '$parentKey' (exit code $($export.ExitCode)). Aborting."
            } else {
                Write-Host "Parent key exported to $BackupFile. Note: backup contains parent key, not the exact subkey path."
                # update exportTarget to parent for informational purposes
                $exportTarget = $parentKey
            }
        } else {
            Write-ErrAndExit "reg export failed and no parent key available. Aborting."
        }
    } catch {
        Write-ErrAndExit "reg export failed and parent export attempt raised error: $_"
    }
} else {
    Write-Host "Backup exported."
}

# Parse hive and subkey
if ($KeyPath -match '^(HKCU|HKLM|HKCR|HKU|HKCC):\\(.+)$') {
    $hive = $matches[1]
    $sub = $matches[2]
} else {
    Write-ErrAndExit "Invalid KeyPath format"
}

# Map hive to base key
switch ($hive) {
    'HKCU' { $base = [Microsoft.Win32.Registry]::CurrentUser }
    'HKLM' { $base = [Microsoft.Win32.Registry]::LocalMachine }
    'HKCR' { $base = [Microsoft.Win32.Registry]::ClassesRoot }
    'HKU'  { $base = [Microsoft.Win32.Registry]::Users }
    'HKCC' { $base = [Microsoft.Win32.Registry]::CurrentConfig }
    default { Write-ErrAndExit "Unsupported hive: $hive" }
}

# Open key for read/write
try {
    $key = $base.OpenSubKey($sub, $true)
} catch {
    Write-ErrAndExit "Failed to open registry key: $KeyPath. $_"
}
if (-not $key) { Write-ErrAndExit "Registry key not found: $KeyPath" }

# Read existing value and kind
try {
    $currentValue = $key.GetValue($ValueName, $null)
    $currentKind = $key.GetValueKind($ValueName)
} catch {
    # If value does not exist GetValueKind throws. We'll treat as string by default.
    $currentValue = $null
    $currentKind = [Microsoft.Win32.RegistryValueKind]::String
}

Write-Host "Current value kind: $currentKind"
if ($null -ne $currentValue) { Write-Host "Current value (raw): $currentValue" } else { Write-Host "Value did not exist previously; will create as string or binary based on default." }

# Attempt set
try {
    switch ($currentKind) {
        'Binary' {
            # Convert ASCII string to bytes
            $bytes = [System.Text.Encoding]::ASCII.GetBytes($valueToSet)
            $key.SetValue($ValueName, $bytes, [Microsoft.Win32.RegistryValueKind]::Binary)
        }
        'DWord' {
            # Try to parse integer from provided string
            $num = 0
            if ([int]::TryParse($valueToSet, [ref]$num)) {
                $key.SetValue($ValueName, $num, [Microsoft.Win32.RegistryValueKind]::DWord)
            } else {
                Write-Host "Provided value is not an integer; writing as string instead (preserving original as backup)."
                $key.SetValue($ValueName, $valueToSet, [Microsoft.Win32.RegistryValueKind]::String)
            }
        }
        'ExpandString' {
            $key.SetValue($ValueName, $valueToSet, [Microsoft.Win32.RegistryValueKind]::String)
        }
        'MultiString' {
            $key.SetValue($ValueName, $valueToSet, [Microsoft.Win32.RegistryValueKind]::String)
        }
        'String' {
            $key.SetValue($ValueName, $valueToSet, [Microsoft.Win32.RegistryValueKind]::String)
        }
        default {
            # default to string
            $key.SetValue($ValueName, $valueToSet, [Microsoft.Win32.RegistryValueKind]::String)
        }
    }

    Write-Host "Value written. Verifying..."
    $new = $key.GetValue($ValueName)
    $newKind = $key.GetValueKind($ValueName)
    Write-Host "Read back kind: $newKind"
    if ($newKind -eq [Microsoft.Win32.RegistryValueKind]::Binary) {
        # show as ASCII if printable
        try {
            $astext = [System.Text.Encoding]::ASCII.GetString($new)
            Write-Host "Read back (as ASCII): $astext"
        } catch { Write-Host "Read back (binary): $new" }
    } else { Write-Host "Read back: $new" }

} catch {
    Write-Error "Failed to write registry value: $_"
    Write-Host "Attempting to restore from backup: $BackupFile"
    if (Test-Path $BackupFile) {
        Start-Process -FilePath reg -ArgumentList "import `"$BackupFile`"" -NoNewWindow -Wait
        Write-Host "Restore attempted."
    }
    exit 1
}

Write-Host "Done."