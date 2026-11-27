# ARK-10

**A fresh start for the ARK series.** ARK-10 is a free Python desktop chat application built with Pygame.

## RC1 features

- Modern resizable desktop chat interface
- Offline mode with built-in responses (no account or API key)
- Optional Local AI mode using an Ollama server running on your computer
- Conversation history saved locally
- Settings saved locally
- Background AI requests so the window remains responsive
- Clear connection errors instead of silently crashing

## Requirements

- Python 3.13 or newer
- Pygame 2.6.1

## Install

```bash
python -m pip install -r requirements.txt
python ARK10.py
```

## Modes

- **Offline:** Works immediately. It is a lightweight built-in chat mode, not a full language model.
- **Local AI:** Press **F2** to switch modes. This mode expects Ollama at `http://localhost:11434` and the `llama3.2` model. Install and start Ollama separately, then make sure the model is available locally.

The default mode is Offline. ARK-10 does not require a paid subscription, API key, or cloud account.

## Data and privacy

Chat history and settings are stored in `~/.ark10/` on your computer. No telemetry is included. Local AI requests go to the Ollama endpoint configured in the source code.

## Keyboard shortcuts

| Key | Action |
| --- | --- |
| Enter | Send message |
| F2 | Switch Offline / Local AI |
| Escape | Quit |

## Project status

**ARK-10 RC1 — initial foundation.** This is an early release; test it and report bugs before treating it as stable.
