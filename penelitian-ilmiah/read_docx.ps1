Add-Type -AssemblyName System.IO.Compression.FileSystem
$docxPath = 'c:\Users\Muhammad Fauza\penelitian-ilmiah\naskah PI\PI_Muhammad_Fauza_REVISED.docx'
$zip = [System.IO.Compression.ZipFile]::OpenRead($docxPath)
$entry = $zip.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }
$stream = $entry.Open()
$reader = New-Object System.IO.StreamReader($stream)
$xmlContent = $reader.ReadToEnd()
$reader.Close()
$stream.Close()
$zip.Dispose()
$xmlDoc = [xml]$xmlContent
$ns = New-Object System.Xml.XmlNamespaceManager($xmlDoc.NameTable)
$ns.AddNamespace('w', 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')
$paragraphs = $xmlDoc.SelectNodes('//w:p', $ns)
foreach ($p in $paragraphs) {
    $texts = $p.SelectNodes('.//w:t', $ns)
    $line = ($texts | ForEach-Object { $_.'#text' }) -join ''
    Write-Output $line
}
