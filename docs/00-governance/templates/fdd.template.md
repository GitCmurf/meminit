---
document_id: { { document_id } }
type: { { type } }
title: { { title } }
status: { { status } }
version: "0.1"
last_updated: { { date } }
owner: { { owner } }
area: { { area } }
docops_version: "2.0"
template_type: fdd-standard
template_version: "2.0"
---

<!-- MEMINIT_METADATA_BLOCK -->

> **Document ID:** {{document_id}}
> **Owner:** {{owner}}
> **Status:** {{status}}
> **Version:** 0.1
> **Last Updated:** {{date}}
> **Type:** {{type}}

<!-- MEMINIT_SECTION: title -->

# {{document_id}}: {{title}}

<!-- AGENT: The title should be concise and descriptive of the feature. -->

<!-- MEMINIT_SECTION: toc -->

## Table of Contents

<!-- AGENT: Generate a table of contents with anchor links to all numbered sections. -->

1. [Executive Summary](#1-executive-summary)
2. [Feature Overview](#2-feature-overview)
3. [User Stories](#3-user-stories)
4. [Functional Requirements](#4-functional-requirements)
5. [Technical Design](#5-technical-design)
6. [Dependencies](#6-dependencies)
7. [Open Questions](#7-open-questions)
8. [Version History](#8-version-history)

<!-- MEMINIT_SECTION: executive_summary -->

## 1. Executive Summary

<!-- AGENT: Write a 2-3 sentence summary. What is being built, for whom, and why now? -->

[Summary here]

<!-- MEMINIT_SECTION: overview -->

## 2. Feature Overview

<!-- AGENT: Describe the feature at a high level. What problem does it solve? Who is it for? -->

[Describe the feature here]

<!-- MEMINIT_SECTION: user_stories -->

## 3. User Stories

<!-- AGENT: List user stories with acceptance criteria. -->

| Story     | As a   | I want to | So that   | Acceptance Criteria |
| --------- | ------ | --------- | --------- | ------------------- |
| [Story 1] | [role] | [action]  | [benefit] | [criteria]          |
| [Story 2] | [role] | [action]  | [benefit] | [criteria]          |

<!-- MEMINIT_SECTION: requirements -->

## 4. Functional Requirements

<!-- AGENT: List functional requirements with clear acceptance criteria. -->

- [FR-1] [Requirement description]
  - Acceptance Criteria: [criteria]
- [FR-2] [Requirement description]
  - Acceptance Criteria: [criteria]

<!-- MEMINIT_SECTION: design -->

## 5. Technical Design

<!-- AGENT: Describe the technical approach. Include architecture, data models, and key algorithms. -->

### Architecture

[Architecture description]

### Data Models

[Data models]

### API Endpoints

[API endpoints if applicable]

<!-- MEMINIT_SECTION: dependencies -->

## 6. Dependencies

<!-- AGENT: List internal and external dependencies. -->

- [Dependency 1]: [Description and impact]
- [Dependency 2]: [Description and impact]

<!-- MEMINIT_SECTION: open_questions -->

## 7. Open Questions

<!-- AGENT: List unresolved questions that need answers before implementation. -->

- [Question 1]
- [Question 2]

<!-- MEMINIT_SECTION: version_history -->

## 8. Version History

<!-- AGENT: Track version changes with dates, authors, and change summaries. -->

| Version | Date     | Author    | Changes       |
| ------- | -------- | --------- | ------------- |
| 0.1     | {{date}} | {{owner}} | Initial draft |
