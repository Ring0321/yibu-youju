# Third-party notices and source boundaries

## Imported application baseline

- Project: [Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template)
- Locked source commit: `cb740b656d7a0a6c5e12c7bf8e50343ec94ee9c7`
- Location in this repository: `baseline/`
- License: MIT; original notice retained verbatim in [baseline/LICENSE](baseline/LICENSE).
- Original copyright: Copyright (c) 2019 Sebastián Ramírez.

The baseline began as an allowlisted working-copy export, not the upstream Git history. Subsequent project changes are recorded in Git. Upstream tracked environment files, deployment workflows, agent instructions, screenshots and local execution data were not copied. The project-specific G0 scripts, infrastructure harness and configuration are additions, not upstream features.

The public G0 runner invokes Docker directly instead of a machine-specific command wrapper. Text line endings are normalized to LF for reproducible cross-platform checkouts. The original upstream working copy was not overwritten. [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) retains original source hashes; changed imported files additionally retain their first exported hash and current published hash. New project files are tracked in Git. These records establish provenance, not a complete dependency-security audit.

## Dependencies and planned components

Dependency metadata is retained in `baseline/uv.lock`, `baseline/bun.lock`, and the package manifests. Installed dependency trees and container images are not redistributed here. Dependencies retain their own licenses.

LangGraph 1.2.12, langgraph-checkpoint-postgres 3.1.2 and Procrastinate 3.10.0 are now pinned library dependencies used by the isolated G0 harness. Runtime acceptance is reported separately in the project verification records. Their MIT licenses remain with their respective distributions; no library source is vendored or relicensed here. Primary sources: [LangGraph](https://github.com/langchain-ai/langgraph), [Procrastinate](https://github.com/procrastinate-org/procrastinate/tree/3.10.0).

pgvector and document parsers remain planned or evaluated components. No code from alternative platforms such as Dify, Chatwoot or RAGFlow is bundled in this export.

## Documentation and media

- Original project additions, research code, documentation and PlantUML sources are offered under the root MIT license, except separately attributed material.
- The two `*_ai.png` concept images are AI-generated explanatory illustrations. They are not screenshots, product photographs or experimental evidence; generated asset rights remain subject to applicable rights and provider terms.
- Third-party product names and logos remain with their respective owners. This repository grants no trademark rights and implies no endorsement by Anker, eufy, FastAPI or other referenced organizations.
- External papers, manuals and websites are linked as references, not republished or relicensed.

Competition reuse permission is separate from the source-code license and has not been confirmed by this repository.
