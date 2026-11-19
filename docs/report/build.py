"""Build from the committed chapter and figure sources. Requires Pandoc and TeX Live/MiKTeX."""
import csv
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    with (ROOT / "figure/test.tsv").open(encoding="utf-8", newline="") as source:
        scores = {(r["run"], r["metric"]): float(r["mean"]) for r in
                  csv.DictReader(source, delimiter="\t") if r["source"] == "gold"}
    table = [r"\begin{center}\begin{tabular}{lrrr}\toprule",
             r"Sistema & nDCG@10 & P@5 & MRR@10 \\\midrule"]
    for profile, label in zip(("E0-v1", "E1-v1", "E2-v1", "E3-v1", "E4-v1", "wikimedia"),
                          ("E0 · standard", "E1 · italiano", "E2 · titolo", "E3 · refusi",
                           "E4 · frase", "Wikimedia")):
        values = [f"{scores[profile, metric]:.4f}".replace(".", ",")
                  for metric in ("nDCG@10", "P@5", "MRR@10")]
        table.append(" & ".join([label, *values]) + r" \\")
    table.append(r"\bottomrule\end{tabular}\end{center}")
    (ROOT / "figure/risultati-test.tex").write_text("\n".join(table) + "\n", encoding="utf-8")
    chapters = sorted((ROOT / "capitoli").glob("*.md"))
    run("pandoc", *chapters, "--standalone", "--template=template.tex", "--citeproc",
        "--bibliography=fonti.bib", "--csl=ieee.csl", "--metadata=link-citations:true", "--metadata=lang:it-IT", "--top-level-division=section",
        "--wrap=preserve", "-o", "newsfinder.tex")
    # Git for Windows includes Perl, which MiKTeX's latexmk wrapper needs.
    if os.name == "nt" and not shutil.which("perl"):
        git_bin = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/usr/bin"
        if (git_bin / "perl.exe").exists():
            os.environ["PATH"] += os.pathsep + str(git_bin)
    if shutil.which("latexmk") and (os.name != "nt" or shutil.which("perl")):
        run("latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error",
            "-outdir=build", "newsfinder.tex")
    else:
        for _ in range(2):
            run("xelatex", "-interaction=nonstopmode", "-halt-on-error",
                "-output-directory=build", "newsfinder.tex")
    info = subprocess.check_output(["pdfinfo", build / "newsfinder.pdf"])
    pages = int(next(line.split()[1] for line in info.splitlines() if line.startswith(b"Pages:")))
    if not 15 <= pages <= 20:
        raise ValueError(f"Expected 15–20 pages, found {pages}")
    shutil.copyfile(build / "newsfinder.pdf", ROOT / "newsfinder.pdf")
    print(f"newsfinder.pdf: {pages} pagine")


if __name__ == "__main__":
    main()
