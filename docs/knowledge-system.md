# Knowledge System Architecture

## Overview

The PABADA knowledge system wraps existing SQLite tables as CrewAI `BaseKnowledgeSource` instances, providing agents with automatic RAG (Retrieval-Augmented Generation) over project data. An `AgentMemoryService` handles persistent memory across agent runs.

## Components

### Knowledge Sources (`backend/knowledge/sources.py`)

Four `BaseKnowledgeSource` subclasses back the knowledge layer:

| Source | Table | Description |
|---|---|---|
| `FindingsKnowledgeSource` | `findings` | Research findings with confidence scores and types |
| `WikiKnowledgeSource` | `wiki_pages` | Project wiki pages |
| `ReferenceFilesKnowledgeSource` | `reference_files` | Reference documents (reads file content from disk) |
| `ReportsKnowledgeSource` | `artifacts` | Research reports (type='report') |

Each source implements `load_content()` to fetch data from SQLite via `execute_with_retry` and `add()` to chunk and save to the vector store.

### KnowledgeService (`backend/knowledge/service.py`)

Central service for managing knowledge sources:

- `configure_embedder(settings)` — returns embedder config dict from environment settings
- `get_sources_for_project(project_id)` — returns all 4 sources scoped to a project
- `get_sources_for_role(role, project_id)` — returns role-appropriate subset

#### Role-to-Source Mapping

| Role | Sources |
|---|---|
| `researcher` | All 4 sources |
| `research_reviewer` | Findings, Wiki, Reports |
| `team_lead` | Wiki, Findings (confidence >= 0.6) |
| `project_lead` | Wiki, Findings (confidence >= 0.7) |
| `developer` | Wiki, ReferenceFiles |
| `code_reviewer` | Wiki |

### AgentMemoryService (`backend/knowledge/memory.py`)

Manages agent memory lifecycle:

- `load_agent_memory(agent_id, project_id)` — loads from `roster.memory` + `knowledge` table
- `persist_agent_memory(agent_id, memory_text)` — saves to `roster.memory`
- `build_memory_context_for_backstory(agent_id, project_id)` — formats memory for backstory injection

### SearchKnowledgeTool (`backend/tools/knowledge/search_knowledge.py`)

Agent-facing tool for explicit cross-source search using FTS5. Complements the automatic CrewAI RAG with an on-demand search capability across findings, wiki, and reference files.

## Data Flow

```
ResearchFlow
  ├── KnowledgeService.get_sources_for_role()
  │     └── SQLite DB → FindingsSource, WikiSource, etc.
  ├── AgentMemoryService.build_memory_context_for_backstory()
  │     └── roster.memory + knowledge table → formatted string
  ├── PabadaAgent(knowledge_sources=[...], memory_service=...)
  │     └── crewai.Agent with RAG and memory-enriched backstory
  └── AgentMemoryService.persist_agent_memory()
        └── Saves output summary back to roster.memory
```

## SearchKnowledgeTool vs CrewAI RAG

| Aspect | SearchKnowledgeTool | CrewAI RAG |
|---|---|---|
| Invocation | Explicit tool call by agent | Automatic on every query |
| Control | Agent chooses when and what to search | Always-on context retrieval |
| Sources | FTS5 full-text search | Vector similarity search |
| Use case | Targeted lookups, specific queries | Background context enrichment |

Use both together: RAG provides ambient context, while SearchKnowledgeTool lets agents do focused searches when they need specific information.

## Embedding Configuration

Set via environment variables (prefixed with `PABADA_`):

| Variable | Default | Description |
|---|---|---|
| `PABADA_EMBEDDING_PROVIDER` | `openai` | Provider: openai, azure, google, ollama |
| `PABADA_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model name |
| `PABADA_EMBEDDING_BASE_URL` | (none) | Base URL override for local models |
| `PABADA_KNOWLEDGE_CHUNK_SIZE` | `1000` | Characters per chunk |
| `PABADA_KNOWLEDGE_CHUNK_OVERLAP` | `200` | Overlap between chunks |

## Adding a New Knowledge Source

1. Create a new `BaseKnowledgeSource` subclass in `backend/knowledge/sources.py`
2. Implement `load_content()` to fetch data from your source
3. Implement `add()` to chunk and save documents
4. Add the source to `KnowledgeService.get_sources_for_project()` and appropriate roles in `get_sources_for_role()`
5. Export from `backend/knowledge/__init__.py`
