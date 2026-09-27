# Third-party notices and source boundaries

## Imported application baseline

- Project: [Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template)
- Locked source commit: `cb740b656d7a0a6c5e12c7bf8e50343ec94ee9c7`
- Location in this repository: `baseline/`
- License: MIT; original notice retained verbatim in [baseline/LICENSE](baseline/LICENSE).
- Original copyright: Copyright (c) 2019 Sebastián Ramírez.

The baseline is an allowlisted working-copy export, not the upstream Git history. Application source and dependency lock files are preserved. Upstream tracked environment files, deployment workflows, agent instructions, screenshots and local execution data were not copied. The project-specific G0 scripts and configuration are additions, not upstream features.

The public G0 runner invokes Docker directly instead of a machine-specific command wrapper. Text line endings are normalized to LF for reproducible cross-platform checkouts. The original workspace remains unchanged. Source and exported file hashes are recorded in [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json); this records provenance, not a complete dependency-security audit.

## Dependencies and planned components

Dependency metadata is retained in `baseline/uv.lock`, `baseline/bun.lock`, and the package manifests. Installed dependency trees and container images are not redistributed here. Dependencies retain their own licenses.

LangGraph, pgvector, document parsers and task queues discussed in the design are planned or evaluated components. Mentioning them is not a claim that they have been installed, integrated or relicensed. No code from alternative platforms such as Dify, Chatwoot or RAGFlow is bundled in this export.

## Documentation and media

- Original project additions, research code, documentation and PlantUML sources are offered under the root MIT license, except separately attributed material.
- The two `*_ai.png` concept images are AI-generated explanatory illustrations. They are not screenshots, product photographs or experimental evidence; generated asset rights remain subject to applicable rights and provider terms.
- Third-party product names and logos remain with their respective owners. This repository grants no trademark rights and implies no endorsement by Anker, eufy, FastAPI or other referenced organizations.
- External papers, manuals and websites are linked as references, not republished or relicensed.

Competition reuse permission is separate from the source-code license and has not been confirmed by this repository.
