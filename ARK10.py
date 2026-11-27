"""
ARK-10 RC1
A free, pygame-based desktop chat application.
Python 3.13+ | Offline mode + optional local Ollama mode
"""
from __future__ import annotations

import json
import queue
import threading
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import pygame

APP_NAME = "ARK-10"
VERSION = "RC3"
WIDTH, HEIGHT = 1920, 1080
BG = (17, 20, 30)
PANEL = (25, 30, 43)
CARD = (34, 40, 56)
ACCENT = (115, 105, 255)
TEXT = (238, 241, 250)
MUTED = (153, 163, 184)
GREEN = (92, 205, 150)
DATA_DIR = Path.home() / ".ark10"
HISTORY_FILE = DATA_DIR / "history.json"
SETTINGS_FILE = DATA_DIR / "settings.json"


def load_json(path: Path, fallback):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return fallback


def save_json(path: Path, value):
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        print(f"ARK-10: could not save {path.name}: {exc}")


def offline_reply(message: str) -> str:
    text = message.strip()
    lower = text.lower()
    if any(word in lower for word in ("hello", "hi", "hey")):
        return "Hello! I'm ARK-10. What would you like to work on?"
    if "your name" in lower or "who are you" in lower:
        return "I'm ARK-10, a free desktop chat assistant. This is Offline mode."
    if "help" in lower:
        return ("I can chat in Offline mode, save this conversation, and switch to "
                "Local AI mode when an Ollama server is running on your computer.")
    if "time" in lower or "date" in lower:
        return "Your computer's date and time: " + datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
    if text.endswith("?"):
        return ("That's a good question. Offline mode uses a small built-in response "
                "engine, so it cannot answer every question yet. Try Local AI mode "
                "for responses from a model running on your computer.")
    return ("I received your message: " + text +
            "\n\nOffline mode is active. Switch to Local AI mode to connect ARK-10 "
            "to a locally running Ollama model.")


def ollama_reply(messages, model: str, endpoint: str) -> str:
    url = endpoint.rstrip("/") + "/api/chat"
    payload = {"model": model, "messages": messages, "stream": False}
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.loads(response.read().decode("utf-8"))
        return result.get("message", {}).get("content", "The local model returned an empty response.")
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Could not reach Ollama. Make sure Ollama is running and the model is installed. "
            "Check Settings for the model name and endpoint. Details: " + str(exc)
        ) from exc
    except (json.JSONDecodeError, KeyError) as exc:
        raise RuntimeError("The local AI server returned an unreadable response.") from exc


class ArkApp:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(f"{APP_NAME} {VERSION}")
        self.screen = pygame.display.set_mode((0, 0), pygame.RESIZABLE)
        self.fullscreen = False
        self.windowed_size = self.screen.get_size()
        self.last_display_toggle = -1000
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("segoeui,arial", 19)
        self.small = pygame.font.SysFont("segoeui,arial", 14)
        self.title_font = pygame.font.SysFont("segoeui,arial", 28, bold=True)
        self.settings = load_json(SETTINGS_FILE, {
            "mode": "Offline",
            "model": "llama3.2",
            "endpoint": "http://localhost:11434",
        })
        self.messages = load_json(HISTORY_FILE, [])
        if not isinstance(self.messages, list):
            self.messages = []
        self.input_text = ""
        self.mode = self.settings.get("mode", "Offline")
        self.model = self.settings.get("model", "llama3.2")
        self.endpoint = self.settings.get("endpoint", "http://localhost:11434")
        self.status = "Ready"
        self.busy = False
        self.results = queue.Queue()
        self.scroll = 0
        self.input_active = True
        self.running = True
        self.settings_open = False
        self.input_rect = pygame.Rect(280, HEIGHT - 78, WIDTH - 315, 54)

    def toggle_display_mode(self):
        """Toggle fullscreen with F11, remembering the windowed dimensions."""
        if self.fullscreen:
            self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
            self.fullscreen = False
        else:
            current_size = self.screen.get_size()
            if current_size[0] > 0 and current_size[1] > 0:
                self.windowed_size = current_size
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            self.fullscreen = True

    def persist(self):
        save_json(HISTORY_FILE, self.messages[-200:])
        save_json(SETTINGS_FILE, {
            "mode": self.mode, "model": self.model, "endpoint": self.endpoint
        })

    def send(self):
        prompt = self.input_text.strip()
        if not prompt or self.busy:
            return
        self.input_text = ""
        self.messages.append({"role": "user", "content": prompt})
        self.persist()
        self.busy = True
        self.status = "Thinking..."
        history = [{"role": m["role"], "content": m["content"]}
                   for m in self.messages[-24:] if m.get("role") in ("user", "assistant")]
        mode, model, endpoint = self.mode, self.model, self.endpoint

        def worker():
            try:
                answer = offline_reply(prompt) if mode == "Offline" else ollama_reply(history, model, endpoint)
                self.results.put(("ok", answer))
            except Exception as exc:
                self.results.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def draw_text(self, text, x, y, color=TEXT, font=None):
        surface = (font or self.font).render(str(text), True, color)
        self.screen.blit(surface, (x, y))
        return surface.get_width()

    def wrap(self, text, max_width):
        words = str(text).split()
        lines, line = [], ""
        for word in words:
            test = (line + " " + word).strip()
            if self.font.size(test)[0] <= max_width:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines or [""]

    def draw(self):
        width, height = self.screen.get_size()
        sidebar_width = max(220, min(280, int(width * 0.15)))
        content_left = sidebar_width + 28
        content_right = width - 28
        content_width = max(300, content_right - content_left)
        conversation_width = min(content_width, 1360)
        conversation_left = content_left + (content_width - conversation_width) // 2
        self.screen.fill(BG)
        pygame.draw.rect(self.screen, PANEL, (0, 0, sidebar_width, height))
        self.draw_text("ARK-10", 24, 22, TEXT, self.title_font)
        self.draw_text(VERSION + "  •  FREE", 25, 60, GREEN, self.small)
        pygame.draw.line(self.screen, (55, 62, 80), (18, 94), (sidebar_width - 18, 94), 1)
        self.draw_text("WORKSPACE", 24, 115, MUTED, self.small)
        pygame.draw.rect(self.screen, (45, 49, 78), (14, 143, sidebar_width - 28, 42), border_radius=9)
        self.draw_text("＋  New conversation", 27, 154, TEXT, self.small)
        self.draw_text("CHAT MODE", 24, 215, MUTED, self.small)
        self.draw_text("●  " + self.mode, 27, 244, GREEN if self.mode == "Offline" else ACCENT)
        self.draw_text("F2 to switch modes", 27, 274, MUTED, self.small)
        self.draw_text("SETTINGS", 27, height - 90, MUTED, self.small)
        self.draw_text("Model: " + self.model, 27, height - 65, TEXT, self.small)

        pygame.draw.rect(self.screen, PANEL, (sidebar_width, 0, width - sidebar_width, 76))
        self.draw_text("New chat", content_left, 22, TEXT, self.title_font)
        status_surface = self.small.render(self.status, True, GREEN if not self.busy else MUTED)
        self.screen.blit(status_surface, (content_right - status_surface.get_width(), 31))
        pygame.draw.line(self.screen, (55, 62, 80), (sidebar_width, 76), (width, 76), 1)

        chat_area = pygame.Rect(conversation_left, 90, conversation_width, max(100, height - 190))
        old_clip = self.screen.get_clip()
        self.screen.set_clip(chat_area)
        y = chat_area.y - self.scroll
        for item in self.messages[-100:]:
            role = item.get("role", "assistant")
            content = item.get("content", "")
            bubble_width = min(max(360, int(chat_area.width * 0.72)), chat_area.width - 24)
            lines = self.wrap(content, bubble_width - 34)
            bubble_height = 24 + len(lines) * 25
            x = chat_area.right - bubble_width - 12 if role == "user" else chat_area.x + 12
            if y + bubble_height >= chat_area.y and y <= chat_area.bottom:
                pygame.draw.rect(self.screen, (54, 52, 91) if role == "user" else CARD,
                                 (x, y, bubble_width, bubble_height), border_radius=12)
                self.draw_text("You" if role == "user" else "ARK-10", x + 16, y + 8,
                               ACCENT if role == "user" else GREEN, self.small)
                for index, line in enumerate(lines):
                    self.draw_text(line, x + 16, y + 29 + index * 25)
            y += bubble_height + 14
        if not self.messages:
            self.draw_text("Welcome to ARK-10", chat_area.x + 12, chat_area.y + 170, TEXT, self.title_font)
            self.draw_text("A clean, free starting point for the ARK series.", chat_area.x + 14, chat_area.y + 212, MUTED)
            self.draw_text("Type a message below to get started.", chat_area.x + 14, chat_area.y + 244, MUTED)
        self.screen.set_clip(old_clip)

        input_width = min(conversation_width, 1360)
        input_left = conversation_left + (conversation_width - input_width) // 2
        self.input_rect = pygame.Rect(input_left, height - 78, input_width - 90, 54)
        pygame.draw.rect(self.screen, CARD, self.input_rect, border_radius=12)
        shown = self.input_text[-90:]
        self.draw_text(shown or "Message ARK-10...", self.input_rect.x + 16,
                       self.input_rect.y + 16, TEXT if shown else MUTED)
        pygame.draw.rect(self.screen, ACCENT, (self.input_rect.right + 12, height - 70, 66, 38), border_radius=9)
        self.draw_text("Send", self.input_rect.right + 23, height - 61, TEXT, self.small)
        pygame.display.flip()

    def handle_results(self):
        try:
            while True:
                kind, value = self.results.get_nowait()
                self.busy = False
                if kind == "ok":
                    self.messages.append({"role": "assistant", "content": value})
                    self.status = "Ready"
                else:
                    self.messages.append({"role": "assistant", "content": "Error: " + value})
                    self.status = "Connection error"
                self.persist()
        except queue.Empty:
            pass

    def run(self):
        while self.running:
            self.handle_results()
            width, height = self.screen.get_size()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
                    self.windowed_size = (max(900, event.w), max(600, event.h))
                    self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 4:
                        self.scroll = max(0, self.scroll - 45)
                    elif event.button == 5:
                        self.scroll += 45
                    elif event.button == 1:
                        if self.input_rect.right < event.pos[0] < self.input_rect.right + 90 and event.pos[1] > height - 90:
                            self.send()
                        elif event.pos[0] < max(220, min(280, int(width * 0.15))) and event.pos[1] > height - 110:
                            self.settings_open = not self.settings_open
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F11:
                        # Ignore OS key-repeat / duplicate F11 events during a mode transition.
                        now = pygame.time.get_ticks()
                        if now - self.last_display_toggle >= 700:
                            self.last_display_toggle = now
                            self.toggle_display_mode()
                    elif event.key == pygame.K_F2:
                        self.mode = "Local AI" if self.mode == "Offline" else "Offline"
                        self.status = "Mode: " + self.mode
                        self.persist()
                    elif event.key == pygame.K_RETURN:
                        self.send()
                    elif event.key == pygame.K_BACKSPACE:
                        self.input_text = self.input_text[:-1]
                    elif event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.unicode and event.unicode.isprintable():
                        self.input_text += event.unicode
            self.draw()
            self.clock.tick(60)
        self.persist()
        pygame.quit()


if __name__ == "__main__":
    try:
        ArkApp().run()
    except Exception as error:
        pygame.quit()
        print(f"ARK-10 stopped safely: {error}")
        raise
