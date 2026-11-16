# iTOL-MCP

> ⚠️ **Unofficial project**: this is an independent community implementation with **no affiliation to
> iTOL / EMBL**, and is not an official MCP server. The iTOL trademark and platform belong to their
> respective owners; when using iTOL services, please comply with their [Terms of Service](https://itol.embl.de/help.cgi#terms).

A self-contained Python package that wraps [iTOL](https://itol.embl.de/) (Interactive Tree Of
Life) phylogenetic-tree visualization as a standard **MCP** (Model Context Protocol) server.
AI assistants can drive the whole pipeline — **tree inspection → taxonomy/monophyly analysis →
iTOL annotation template generation → batch upload → export** — through **33 tools, 3
resources, and 2 guided prompts**.

- Version: 0.1.0 · Python ≥ 3.11 · Deps: mcp==2.3.0 / dendropy / pandas / PyYAML / httpx / pydantic
- Docs: `README.md` (中文), `README_EN.md` (English), `docs/` (tools / templates / configuration / security / faq)

## Feature Overview

| Group | Tools | Capability |
|-------|-------|------------|
| A Workspace & Files | 1–3 | Directory listing, file read/write (workspace whitelist, atomic write, size limits) |
| B Tree Analysis | 4–5 | Tree parse & stats, per-item input validation |
| C Taxonomy | 6–8 | GTDB/embedded/NCBI extraction, monophyly detection, conditional styling |
| D Templates | 9–24 | 32 annotation-template registry, unified + shortcut entries, bundling, validation |
| E iTOL API | 25–30 | ZIP upload, 8-format export, upload-and-export, delete, status probe |
| F System | 31–33 | Server info, health check, API key config |

- **3 resources**: `itol://help/template-types`, `itol://help/batch-api`, `itol://help/palettes`
- **2 prompts**: `itol-visualize-workflow`, `itol-publication-style`

## 30-Second Quick Start

```bash
# 1) Install (python-3.11 env)
python -m pip install -e .

# 2) Write your iTOL API Key (once)
itol-mcp --set-api-key

# 3) Register with an MCP client (see docs/configuration.md):
#    mcpServers.itol-mcp = { "command": "<python-3.11 abs path>/bin/itol-mcp", "args": [], "cwd": "<work dir>" }

# 4) Debug
mcp dev src/itol_mcp/server.py
```

## Example Workflow

> User: "Take a look at `tree.nwk`, add a color strip by Phylum, then upload and export a
> 300-dpi PDF."

LLM tool sequence:

1. `itol_tree_info(tree_file="data/tree.nwk")`
2. `itol_taxonomy_extract(tree_file="data/tree.nwk", format="auto", output="data/tax.csv")`
3. `itol_template_create_color_strip(tree_file="data/tree.nwk", taxonomy_file="data/tax.csv", column="Phylum", output="templates/strip.txt")`
4. `itol_upload_and_export(tree_file="data/tree.nwk", template_files=["templates/strip.txt"], format="pdf", dpi=300, wait=10)`
5. Summarize: tree_id, iTOL link, local PDF path.

## Example Data & Scripts

The repo ships synthetic data (`examples/data/`: 130-tip and 32-tip trees with companion
tables) plus two end-to-end scripts:

- `examples/01_quick_figure.py`: quick figure (color strip + heatmap + one-step upload/export PDF);
- `examples/02_publication_style.py`: publication styling (monophyly + branch coloring + template bundle).

## Development & Testing

```bash
python -m pip install -e ".[dev]"
python -m pytest -q              # unit + golden tests
python -m ruff check src tests examples   # lint
python -m mypy src/itol_mcp      # type checking
```

Test coverage ≥85%. See `CONTRIBUTING.md` for contribution guidelines.

## Security Highlights

- API key via three channels (tool arg > env var > key file), fully redacted, key file chmod 600;
- All file access confined to the workspace whitelist — no path traversal or symlink escape;
- HTTPS-only to the official iTOL domain, with unified timeouts and retry policy;
- See `docs/security.md`; to report a vulnerability, follow `SECURITY.md` (private disclosure).

## Prerequisites

- Upload requires an iTOL **Standard** subscription and API key; export does not require a subscription;
- Data files must live in the workspace directory or be passed as inline text parameters.

## License

MIT (see LICENSE).
