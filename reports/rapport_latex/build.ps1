$ErrorActionPreference = "Stop"

if (-not (Get-Command pdflatex -ErrorAction SilentlyContinue)) {
    throw "pdflatex est introuvable. Installez MiKTeX/TeX Live ou compilez le dossier avec Overleaf."
}

Push-Location $PSScriptRoot
try {
    pdflatex -interaction=nonstopmode -halt-on-error rapport.tex
    if (Get-Command bibtex -ErrorAction SilentlyContinue) {
        bibtex rapport
    }
    pdflatex -interaction=nonstopmode -halt-on-error rapport.tex
    pdflatex -interaction=nonstopmode -halt-on-error rapport.tex
    Write-Host "Rapport généré : $PSScriptRoot\rapport.pdf"
}
finally {
    Pop-Location
}
