$agyBin = "$env:LOCALAPPDATA\agy\bin"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")

if (($userPath -split ';') -notcontains $agyBin) {
    [Environment]::SetEnvironmentVariable(
        "Path",
        "$userPath;$agyBin",
        "User"
    )
}