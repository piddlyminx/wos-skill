# WOS Skill

An AI agent skill for automating Whiteout Survival (WOS) on Android emulators via ADB. Designed to be dropped into an AI coding agent's skills directory (e.g. Claude Code) to give it the ability to control the game, run battles, capture reports, and build testcases for validating a battle simulator.

## Requirements

- **Windows** (native or WSL2)
- **MuMu Player** with one emulator instance per game account you want to control
- **ADB** available on PATH
- **[uv](https://docs.astral.sh/uv/)** for Python dependency management
- An AI coding agent that supports skill directories

## Setup

1. Clone this repo into your agent's skills directory
2. Run `wos/scripts/wosctl` — first run will walk you through onboarding: MuMu paths, emulator instance discovery, and alliance configuration
3. Ask your agent to read [wos/KNOWLEDGE_INDEX.md](wos/KNOWLEDGE_INDEX.md) and explain what it can do for you with this skill — or just tell it what you'd like to do and let it figure it out
