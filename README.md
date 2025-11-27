# Kubernetes Docset Generator for Dash

A Python tool to generate high-quality [Dash](https://kapeli.com/dash) docsets for Kubernetes documentation with enhanced semantic indexing.

## Features

- **Enhanced Indexing**: Extracts 15,600+ searchable entries including:
  - 5,195 API Types (PodSpec, DeploymentStatus, Container, etc.)
  - 4,379 Sections (Volumes, Scheduling, Security Context, etc.)
  - 2,169 Code Samples
  - 910 Properties (field definitions)
  - 819 Guides (concepts, tasks, tutorials)
  - 244 Glossary terms
  - 163 API Resources
  - 90 kubectl Commands
  - 6 Components

- **Multiple Input Sources**:
  - Scrape directly from kubernetes.io (--scrape)
  - Use existing Dash-generated docset (--source)

- **Intelligent Parsing**: Specialized parsers for different documentation types:
  - API reference pages
  - kubectl command documentation
  - Conceptual guides
  - Glossary entries
  - Code samples
  - Embedded Dash anchors

## Requirements

- Python >= 3.14 (or adjust in `pyproject.toml`)
- [uv](https://github.com/astral-sh/uv) package manager

## Installation

```bash
git clone https://github.com/ichoosetoaccept/kubernetes-docset.git
cd kubernetes-docset
```

## Usage

### Option 1: Scrape from kubernetes.io (Recommended)

```bash
uv run python main.py --scrape
```

This will:
1. Download all Kubernetes documentation from kubernetes.io
2. Cache it in `.cache/kubernetes-docs/`
3. Generate a Dash docset in `./output/`

### Option 2: Use Existing Dash-Generated Source

```bash
uv run python main.py --source ~/Library/Application\ Support/Dash/Docset\ Generator/Kubernetes/Kubernetes.docset
```

This option uses a pre-generated docset from Dash's built-in scraper as the source, which may provide additional embedded anchors.

### Custom Options

```bash
# Specify output directory
uv run python main.py --scrape --output ./my-docsets

# Specify Kubernetes version
uv run python main.py --scrape --version 1.34

# Use custom cache directory
uv run python main.py --scrape --cache-dir ./cache
```

## Installation in Dash

After generating the docset:

1. Open Dash
2. Go to Preferences > Docsets
3. Click the + button
4. Select the generated `.docset` file

Or simply double-click the `.docset` file.

## How It Works

### Specialized Parsers

The tool uses multiple specialized parsers that analyze the HTML structure:

1. **DashAnchorParser**: Extracts embedded `dashAnchor` entries from Dash-generated HTML
2. **EnhancedAPIReferenceParser**: Extracts Types, Sections, and Properties from API reference HTML
3. **EnhancedKubectlParser**: Extracts kubectl commands and subcommands
4. **CodeSampleParser**: Identifies Kubernetes manifests in code blocks
5. **APIResourceParser**: Identifies API resources (Pod, Deployment, Service, etc.)
6. **KubectlCommandParser**: Extracts kubectl command documentation
7. **GuideParser**: Indexes conceptual guides and tutorials
8. **GlossaryParser**: Extracts glossary terms
9. **ComponentParser**: Identifies Kubernetes components (kube-apiserver, kubelet, etc.)
10. **FallbackParser**: Catches any unmatched documentation pages

### Parser Priority

All matching parsers run on each file, allowing multiple entry types per page. For example, an API reference page might contribute:
- A Resource entry for the API object
- Multiple Type entries for embedded types (PodSpec, Container, etc.)
- Multiple Section entries for field groups

## Project Structure

```
.
├── main.py                      # CLI entry point
├── k8s_docset/
│   ├── __init__.py
│   ├── builder.py               # Docset builder
│   ├── parsers.py               # Core HTML parsers
│   ├── enhanced_parsers.py      # Enhanced parsers for raw HTML
│   └── scraper.py               # Web scraper for kubernetes.io
├── contrib/                     # Dash contribution files
│   ├── docset.json
│   ├── icon.png
│   └── icon@2x.png
└── pyproject.toml               # Project dependencies
```

## License

MIT License - see [LICENSE](LICENSE) for details.
