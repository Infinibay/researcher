# Infinibay

A prototype multi-agent swarm system for autonomous research, investigation, and software development — designed to run on consumer hardware with small open-weight models (14B parameters and under).

Agents collaborate through an event-driven architecture: a team lead plans work, researchers gather information, developers write code, and reviewers check quality. All orchestrated by flows that react to events in real time.

## Requirements

- **Python 3.12+**
- **Node.js 20+** (for the frontend)
- **Podman** or **Docker** (for sandbox and Forgejo)
- **Ollama** (for local LLM inference)
- A machine with at least 16GB RAM and a GPU with 12GB+ VRAM for 14B models

## Quick Start

```bash
# 1. Clone and enter the repo
git clone https://github.com/your-org/infinibay.git
cd infinibay

# 2. Copy and edit the environment config
cp .env.example .env
# Edit .env — set your LLM model and API key (or use Ollama defaults)

# 3. Start everything
./start.sh
```

`start.sh` handles everything: creates a Python venv, installs dependencies, initializes the database, starts Forgejo (local git server), and launches the backend (`:8000`) + frontend (`:5173`).

Open http://localhost:5173 in your browser.

## Sandbox

When `INFINIBAY_SANDBOX_ENABLED=true`, each agent runs its tools inside an isolated Podman/Docker pod. This means file operations, shell commands, and git operations happen in a container — not on your host machine.

- Each agent gets its own persistent pod with a dedicated workspace
- Pods are created on demand and cleaned up when idle
- GPU passthrough is supported via `INFINIBAY_SANDBOX_GPU_ENABLED=true` (requires nvidia-container-toolkit)

Set `INFINIBAY_SANDBOX_ENABLED=false` for local development without containers.

## Tested Models

The system is designed for small models. Here's what works:

| Model | Speed | Tool Calling | Research | Notes |
|---|---|---|---|---|
| **qwen3.5:27b** | Medium | Excellent | Excellent | Best overall quality, very few hallucinations |
| **gpt-oss:20b** | Fast | Good | Good | Some tool hallucinations |
| **glm-4.7-flash:128k** | Medium | Very good | Good | Strong orchestration |
| **ministral-3:14b** | Very fast | Good | Very good | Medium orchestration |

### Closed-source models

The system works with Gemini, OpenAI, and Anthropic APIs — and they perform well. However, **token consumption is extreme** because the prompts are very explicit and detailed (necessary for small open-weight models to follow instructions reliably). Keep this in mind for cost.

## Configuration

All config uses the `INFINIBAY_` prefix. The essential variables:

```bash
INFINIBAY_LLM_MODEL=ollama_chat/qwen3.5:27b   # LiteLLM format
INFINIBAY_LLM_API_KEY=not-needed               # Only needed for cloud providers
INFINIBAY_LLM_BASE_URL=http://localhost:11434/  # Only for Ollama/custom endpoints
INFINIBAY_SANDBOX_ENABLED=true
```

Embedding provider is auto-detected from your LLM provider. Override with `INFINIBAY_EMBEDDING_PROVIDER` if needed.

See `.env.example` for all options.

## Known Issues

- **UI bugs**: the Stop button doesn't actually stop agents — you need to `Ctrl+C` the backend process.
- **Duplicate tool execution**: some tools (particularly `send_message` and `add_comment`) occasionally fire twice in a single agent step.

## Contributing

This is an early prototype. The best way to contribute right now is:

- Trying it out and reporting bugs
- Sharing feedback on agent behavior
- Suggesting ideas for new capabilities or workflow improvements

Open an issue or start a discussion.

## License

See [LICENSE.md](LICENSE.md).
