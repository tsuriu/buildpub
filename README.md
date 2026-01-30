# 🐳 Docker Auto-Builder & Publisher

![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)
![Docker](https://img.shields.io/badge/docker-required-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A powerful, zero-config Python utility that automates the Docker image lifecycle: **Build**, **Tag**, and **Push**.

It seamlessly integrates with your Git workflow, supporting both remote repository cloning and local development contexts, with built-in auto-versioning capabilities.

## ✨ Key Features

- **🚀 Remote Clone & Build**: Point to any Git URL, and it handles the rest.
- **📍 Local Context Detection**: Run it inside your repo—it auto-detects the root and correct remote.
- **🏷️ Smart Tagging**:
  - Auto-infers image names from your git remote (e.g., `git@github.com:user/app` → `user/app`).
  - **Auto-Versioning**: Automatically bumps your semantic version (patch level) based on the latest Git tag.
- **🔐 Flexible Auth**: Authenticate via CLI arguments, Environment Variables, or existing local sessions.
- **📜 Beautiful Logs**: Clear, colored output to track your build progress.

---

## 🛠️ Installation

### Option 1: Development Usage
If you want to contribute or modify the code:

1. **Set up the Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   
   # Install runtime + dev dependencies
   pip install -e .[dev]
   ```
2. **Run directly**:
   ```bash
   buildpub
   ```

### Option 2: Install as a System Command (Recommended)
You can install this tool globally (or in your user environment) to run it from anywhere.

1. **Install via pip**:
   ```bash
   pip install .
   ```
   *(Run this inside the directory containing `pyproject.toml`)*

2. **Run it from anywhere**:
   ```bash
   buildpub
   ```

---

## 🚀 Quick Start

### 1. Build from your Current Directory (Local Mode)
The most common use case. Go to your project folder and run:
```bash
# This detects the git repo, infers the image name, and builds 'latest'
buildpub
```

### 2. Auto-Version Bump
Automatically detect the latest git tag (e.g., `v1.0.2`), bump it (to `v1.0.3`), build, and push.
```bash
buildpub --auto-version
```

### 3. Build a Remote Repository
Build a specific branch from a remote URL without cloning it manually.
```bash
buildpub \
  --repo https://github.com/Start Bootstrap/startbootstrap-clean-blog.git \
  --image myuser/clean-blog \
  --tag v2.0
```

---

## ⚙️ Usage Reference

```bash
buildpub [OPTIONS]
```

### Core Arguments

| Flag | Description | Default |
|------|-------------|---------|
| `--repo` | Git repository URL. If omitted, checks current directory. | `None` (Local) |
| `--image` | Target Image Name (e.g., `user/repo`). Auto-inferred if omitted. | Inferred |
| `--tag` | Specific tag to use. Overridden if `--auto-version` is set. | `latest` |
| `--auto-version`| **(Flag)** If set, bumps the latest git tag (patch version). | `False` |
| `--dockerfile` | Relative path to the Dockerfile. | `Dockerfile` |

### Environment & Context

| Flag | Description | Default |
|------|-------------|---------|
| `--branch` | Branch to checkout (Only for Remote Build). | `main` |
| `--build-arg` | Pass build arguments (can be used multiple times). <br>Example: `--build-arg ENV=prod` | `None` |

### Authentication

| Flag | Description | Env Variable |
|------|-------------|--------------|
| `--username` | Registry Username | `DOCKER_USERNAME` |
| `--password` | Registry Token/Password | `DOCKER_PASSWORD` |
| `--registry` | Registry URL (e.g., `ghcr.io`) | `None` (Docker Hub) |
| `--verbose`| **(Flag)** Enable verbose logging (INFO level). Default is ERROR only. | `False` |

> **Pro Tip:** For CI/CD environments, use the Environment Variables `DOCKER_USERNAME` and `DOCKER_PASSWORD` instead of flags for better security.

---

## 📦 Examples

### 🔹 Basic Build & Push
```bash
buildpub --tag production
```
_Builds current local code, pushes as `{inferred_name}:production`._

### 🔹 Custom Dockerfile & Args
```bash
buildpub \
  --dockerfile build/Dockerfile.prod \
  --build-arg APP_ENV=production \
  --tag v1.5
```

### 🔹 CI/CD Workflow (with Env Vars)
```bash
export DOCKER_USERNAME="myuser"
export DOCKER_PASSWORD="mysecrettoken"

buildpub --auto-version
```
