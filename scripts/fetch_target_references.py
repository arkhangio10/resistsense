from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen


ASSEMBLY = "GCF_000005845.2_ASM584v2"
BASE_URL = (
    "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/005/845/"
    f"{ASSEMBLY}"
)
PROTEIN_GENES = {"ftsI", "mrcA", "mrcB", "gyrA", "gyrB", "parC", "parE", "folA", "folP"}


def _download(name: str) -> tuple[bytes, str]:
    url = f"{BASE_URL}/{ASSEMBLY}_{name}.gz"
    request = Request(url, headers={"User-Agent": "ResistSense/0.1"})
    with urlopen(request, timeout=120) as response:
        compressed = response.read()
    return gzip.decompress(compressed), hashlib.sha256(compressed).hexdigest()


def _attributes(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in text.split(";"):
        if "=" in item:
            key, value = item.split("=", 1)
            values[key] = value
    return values


def _fasta(text: str) -> dict[str, str]:
    records: dict[str, str] = {}
    identifier: str | None = None
    chunks: list[str] = []
    for line in text.splitlines():
        if line.startswith(">"):
            if identifier is not None:
                records[identifier] = "".join(chunks)
            identifier = line[1:].split()[0]
            chunks = []
        elif identifier is not None:
            chunks.append(line.strip())
    if identifier is not None:
        records[identifier] = "".join(chunks)
    return records


def _wrap(sequence: str, width: int = 80) -> str:
    return "\n".join(sequence[index : index + width] for index in range(0, len(sequence), width))


def main() -> None:
    output_dir = Path("configs/target_references")
    output_dir.mkdir(parents=True, exist_ok=True)
    gff_bytes, gff_source_sha = _download("genomic.gff")
    protein_bytes, protein_source_sha = _download("protein.faa")
    genome_bytes, genome_source_sha = _download("genomic.fna")
    gff = gff_bytes.decode("utf-8")
    proteins = _fasta(protein_bytes.decode("utf-8"))
    genome = _fasta(genome_bytes.decode("utf-8"))

    protein_ids: dict[str, tuple[str, int]] = {}
    rrs_location: tuple[str, int, int, str] | None = None
    for line in gff.splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 9:
            continue
        seqid, _, feature, start, end, _, strand, _, raw_attributes = fields
        attributes = _attributes(raw_attributes)
        gene = attributes.get("gene")
        if feature == "CDS" and gene in PROTEIN_GENES:
            protein_id = attributes.get("protein_id")
            length = int(end) - int(start) + 1
            if protein_id and (
                gene not in protein_ids or length > protein_ids[gene][1]
            ):
                protein_ids[gene] = (protein_id, length)
        if feature == "rRNA" and gene == "rrsA":
            rrs_location = (seqid, int(start), int(end), strand)

    missing = sorted(PROTEIN_GENES.difference(protein_ids))
    if missing or rrs_location is None:
        raise RuntimeError(f"NCBI reference lacks required targets: {missing}")

    protein_lines: list[str] = []
    for gene in sorted(PROTEIN_GENES):
        protein_id = protein_ids[gene][0]
        sequence = proteins.get(protein_id)
        if not sequence:
            raise RuntimeError(f"Protein sequence unavailable for {gene}:{protein_id}")
        protein_lines.extend(
            [f">{gene}|{protein_id}|{ASSEMBLY}", _wrap(sequence)]
        )
    protein_path = output_dir / "ecoli_k12_targets.faa"
    protein_path.write_text("\n".join(protein_lines) + "\n", encoding="ascii")

    seqid, start, end, strand = rrs_location
    rrs = genome[seqid][start - 1 : end]
    if strand == "-":
        complement = str.maketrans("ACGT", "TGCA")
        rrs = rrs.translate(complement)[::-1]
    rrs_path = output_dir / "ecoli_k12_rrs.fna"
    rrs_path.write_text(
        f">rrs|rrsA|{seqid}:{start}-{end}\n{_wrap(rrs)}\n", encoding="ascii"
    )

    manifest = {
        "assembly": ASSEMBLY,
        "source": "NCBI RefSeq E. coli K-12 MG1655",
        "base_url": BASE_URL,
        "source_compressed_sha256": {
            "genomic.gff.gz": gff_source_sha,
            "protein.faa.gz": protein_source_sha,
            "genomic.fna.gz": genome_source_sha,
        },
        "outputs": {
            protein_path.name: hashlib.sha256(protein_path.read_bytes()).hexdigest(),
            rrs_path.name: hashlib.sha256(rrs_path.read_bytes()).hexdigest(),
        },
        "protein_ids": {
            gene: protein_ids[gene][0] for gene in sorted(PROTEIN_GENES)
        },
        "rrs_reference": {
            "gene": "rrsA",
            "sequence_id": seqid,
            "start": start,
            "end": end,
            "strand": strand,
        },
    }
    (output_dir / "reference_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
