param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$rawDir = Join-Path $projectRoot "data\raw\bvbrc"
$artifactDir = Join-Path $projectRoot "artifacts\phase2"
$astPath = Join-Path $rawDir "ecoli_phase2_selected_lab.tsv"
$genomePath = Join-Path $rawDir "ecoli_genome_quality.tsv"

New-Item -ItemType Directory -Force -Path $rawDir, $artifactDir | Out-Null

$astUrl = "https://www.bv-brc.org/api/genome_amr/?and(eq(taxon_id,562),eq(evidence,Laboratory%20Method),in(antibiotic,(ciprofloxacin,ampicillin,cefotaxime,gentamicin,trimethoprim%2Fsulfamethoxazole)),in(resistant_phenotype,(Resistant,Susceptible)))&select(id,genome_id,genome_name,antibiotic,resistant_phenotype,measurement_value,measurement_unit,laboratory_typing_method,testing_standard,testing_standard_year,source,evidence,pmid)&sort(+id)&limit(100000)&http_download=true"
$genomeUrl = "https://www.bv-brc.org/api/genome/?eq(taxon_id,562)&select(genome_id,genome_name,genome_status,genome_quality,genome_length,contigs,contig_n50,checkm_completeness,checkm_contamination,coarse_consistency,fine_consistency,partial_cds,assembly_accession,cgmlst_hc50,collection_year,isolation_country,host_name)&sort(+genome_id)&limit(200000)&http_download=true"

curl.exe --fail --compressed --retry 3 -H "Accept: text/tsv" --output $astPath $astUrl
if ($LASTEXITCODE -ne 0) { throw "BV-BRC AST download failed" }

curl.exe --fail --compressed --retry 3 -H "Accept: text/tsv" --output $genomePath $genomeUrl
if ($LASTEXITCODE -ne 0) { throw "BV-BRC genome metadata download failed" }

& $PythonExe (Join-Path $PSScriptRoot "audit_phase2.py") `
    --input $astPath `
    --genome-metadata $genomePath `
    --output-dir $artifactDir

if ($LASTEXITCODE -ne 0) { throw "Phase 2 audit failed" }

