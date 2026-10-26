# Yorvyn Documentation Portal

Welcome to the centralized documentation directory for the Yorvyn AI Fashion & 3D Garment platform.

---

## 🏛️ Architecture & System Design
- [Project Structure & Layered Architecture](file:///Users/anujsandhu/Projects/yorvyn/docs/architecture/project-structure.md): Comprehensive guide on the Spring Boot/Maven-inspired layout, directory placement, and feature boundaries.
- [File Migration & Semantic Renaming Map](file:///Users/anujsandhu/Projects/yorvyn/docs/architecture/file-migration-map.md): Full audit of migrated files, before/after paths, semantic improvements, and verification status.
- [Technology Library Map](file:///Users/anujsandhu/Projects/yorvyn/docs/architecture/technology-library-map.md): Yorvyn's 12 modular technology packages, responsibilities, algorithms, and interfaces.
- [AI Stylist & Voice Architecture Plan](file:///Users/anujsandhu/Projects/yorvyn/docs/architecture/ai-stylist-plan.md): Comprehensive dual-mode voice/text chat, multi-provider LLM engine, and speech pipeline plan.
- [Real Dataset Pipeline](file:///Users/anujsandhu/Projects/yorvyn/docs/architecture/dataset-pipeline.md): Official Fashion-MNIST ingestion, binary ubyte parser, and ML evaluation benchmarks.
- [AI Model Licensing & Governance](file:///Users/anujsandhu/Projects/yorvyn/docs/architecture/model-licensing.md): Provenance, compliance boundaries, and quarantine of non-commercial datasets (DeepFashion).
- [Real Fashion Dataset Registry](file:///Users/anujsandhu/Projects/yorvyn/research/datasets/registry.md): Catalog of verified and gated datasets with SHA-256 hashes and license terms.
- [Backend Migration Audit (Firebase to Supabase + Cloudinary)](file:///Users/anujsandhu/Projects/yorvyn/docs/architecture/backend-migration-audit.md): Complete audit of Firebase dependencies, Supabase PostgreSQL schema, and Cloudinary image storage pipeline.
- [Module Boundaries & Clean Interfaces](file:///Users/anujsandhu/Projects/yorvyn/docs/architecture/module-boundaries.md): Package boundary rules, zero-cycle dependency standards, and import guidelines.
- [Integration Roadmap](file:///Users/anujsandhu/Projects/yorvyn/docs/architecture/integration-roadmap.md): Milestone plan for progressive component enhancement.

---

## 💻 Development & Engineering Standards
- [File Naming & Code Conventions](file:///Users/anujsandhu/Projects/yorvyn/docs/development/file-naming-conventions.md): Detailed conventions for React (PascalCase), Hooks (useCamelCase), Python modules (snake_case), and prohibition of third-party branding.
- [Supabase PostgreSQL Schema Migration 001](file:///Users/anujsandhu/Projects/yorvyn/backend/migrations/001_initial_supabase_schema.sql): Initial schema with 8 tables, indexes, and comprehensive Row Level Security policies.

---

## 🔍 Audits & Verifications
- [Independent Technology Library Integration Audit](file:///Users/anujsandhu/Projects/yorvyn/docs/audits/library-integration-audit.md): Evidence-based verification of package independence, runtime self-sufficiency, and upstream isolation.
- [Photo-to-3D Garment Pipeline Audit](file:///Users/anujsandhu/Projects/yorvyn/docs/audits/garment-pipeline-audit.md): Multi-layer verification of garment geometry synthesis, PBR texture baking, and user privacy guarantees.

---

## ⚙️ Operations & Deployment
- [Restore & Rollback Procedures](file:///Users/anujsandhu/Projects/yorvyn/docs/operations/restore-and-rollback.md): Safe stash, rollback points, and GitHub backup workflow.
- [Supabase & Cloudinary Rollback Runbook](file:///Users/anujsandhu/Projects/yorvyn/docs/operations/rollback-supabase-cloudinary.md): Operational procedures for rollback, dual-mode operation, and account recovery.
- [Third-Party Notices & Licenses](file:///Users/anujsandhu/Projects/yorvyn/licenses/THIRD_PARTY_NOTICES.md): Attribution, copyright preservation, and SPDX licenses for all upstream projects.
