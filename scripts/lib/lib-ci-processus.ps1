# lib-ci-processus.ps1 - la table des processus de Windows, lue par lib-ci-arbre.sh (#2270).
#
# Une ligne par processus, separee par des tabulations :
#   pid  ppid  debut (secondes unix)  nom  ligne de commande
# Windows ne rattache JAMAIS un orphelin a un autre pere : le ppid d'un enfant
# reste celui du pere mort. C'est ce qui permet de retrouver un arbre dont la racine
# a disparu (kill -9 du rejeu), la ou `taskkill /T` ne trouve plus rien.
# Fichier ASCII seulement : PowerShell 5 lit un script sans BOM en ANSI.
$o = New-Object System.Text.StringBuilder
Get-CimInstance Win32_Process | ForEach-Object {
  $c = ''
  if ($_.CommandLine) { $c = ($_.CommandLine -replace '[\t\r\n]+', ' ') }
  $t = 0
  if ($_.CreationDate) { $t = [int64](([datetimeoffset]$_.CreationDate).ToUnixTimeSeconds()) }
  [void]$o.Append(("{0}`t{1}`t{2}`t{3}`t{4}`n" -f $_.ProcessId, $_.ParentProcessId, $t, $_.Name, $c))
}
[Console]::Out.Write($o.ToString())
