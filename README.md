# CIIE Remote Labs

> [Leer en español](./README.es.md)

A university project for remote control of robots in laboratories. Users interact through a web frontend, which communicates with a Python backend (FastAPI) that bridges to robots managed via ROS.

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Conventions](#conventions)
- [Environment Variables](#environment-variables)
- [Contributing Guide](#-welcome-to-ciie_remote_labs-project-repository)
  - [Prerequisites](#-prerequisites)
  - [SSH Key Setup](#1️⃣-set-up-your-ssh-key-and-link-it-to-gitlab)
  - [Clone the Repo](#2️⃣-clone-your-repo)
  - [Branching](#3️⃣-create-a-new-branch-for-each-edit)
  - [Commits & Push](#4️⃣-make-commits-and-push-your-code)
  - [Merge Requests](#5️⃣-create-a-merge-request-mr)
  - [MR Best Practices](#good-practices-for-merge-requests-mrs)
- [Docker Deploy](#docker-deploy)
- [Raspberry Pi Configs](#raspberry-pi-configs)

## Architecture

For a detailed description of the system architecture, communication flows, data model, and deployment, see [Documents/arquitectura.md](./Documents/arquitectura.md).

```
[Frontend] → [API (FastAPI)] → [ROS] → [RaspberryPi] → [Arduino/Robot]
                  ↕
              [PostgreSQL]
```

## Project Structure

| Directory | Status | Description |
|-----------|--------|-------------|
| `Api/` | Active (WIP) | FastAPI backend — main system entry point |
| `RaspberryPi/` | Active | Robot-side controller (behavior + communication) |
| `Db/` | Active | PostgreSQL schema, migrations (dbmate), seed data |
| `Arduino/` | Active | Robot firmware (7-servo arm control) |
| `ros_tryouts/` | Active | ROS 2 workspace for robot management |
| `Documents/` | Active | General system documentation |
| `Web/` | Deprecated | Old PHP frontend |
| `Python/` | Deprecated | Legacy scripts |

## Tech Stack

- **Backend**: Python 3.13.7+, FastAPI, SQLModel
- **Database**: PostgreSQL 17.5
- **Auth**: JWT (HS256) + bcrypt
- **Real-time**: WebSockets + aioreactive
- **Protocol**: JSON-RPC 2.0 (robot commands)
- **Package manager**: uv (workspace)
- **Deployment**: Docker Compose
- **Migrations**: dbmate

## Quick Start

### Prerequisites

- Python 3.13.7+
- uv package manager
- Docker & Docker Compose

### 1. Create the Docker network

```bash
docker network create ciie-test
```

### 2. Start the database

```bash
cd Db
make up_db.dev.detached    # Start PostgreSQL in background
make migrate_db            # Run migrations
make seed_apply            # Apply seed data
```

### 3. Start the API

```bash
cd Api
make up_dev
```

### 4. Start the RaspberryPi mock (demo mode)

```bash
cd RaspberryPi
# Set MOCK_ROBOT=1 in .env for demo mode (no physical hardware needed)
make up_dev
```

## Conventions

- **Docker**: every subproject runs via Docker/Docker Compose
- **Demo mode**: the entire project can run without physical hardware (RaspberryPi mock)
- **Makefiles**: every subproject uses a Makefile as a unified command entry point
- **READMEs**: bilingual — `README.md` (English) and `README.es.md` (Spanish)
- **Documentation**: written in Spanish
- **Code comments**: Spanish or English

## Environment Variables

**Api** (required):
- `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_URL`
- `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`

**RaspberryPi** (`.env.defaults` has defaults):
- `SERVER_URL`, `ARDUINO_PORT`, `MOCK_ROBOT`, `CREATE_DEFAUL_METADATA`

See each subproject's README for details.

---

## 🚀 Welcome to CIIE_Remote_Labs Project Repository

This guide will walk you through the **first steps** to start contributing to this project. Even if it's your **first time using GitLab or Git**, don't worry — we've got you covered.

---

## 📌 Prerequisites

- A **GitLab** account → https://gitlab.com
- **Git** installed → https://git-scm.com/downloads
- Terminal access on your machine

---

## 1️⃣ Set up your SSH key and link it to GitLab
An SSH Key is a secure authentication method used to connect to Git servers without using a password.

1. Generate a new SSH key:
        Go to your Terminal and execute:
```bash
    ssh-keygen -t ed25519 -C "your_email@example.com"
```
        Then press Enter to  accept the default file location.

2. Start the SSH agent and add your key:
```bash
    eval "$(ssh-agent -s)"
    ssh-add ~/.ssh/id_ed25519
```

3. Copy the following output, this will be your public key:
 ```bash
    cat ~/.ssh/id_ed25519.pub
```
4. Go to gitlab -> Preferences -> SSH key
5. Paste the key, give it a name and click on **add key**

## 2️⃣ Clone your Repo
**Why Clone a repository?**
Cloning the repo to your local machine lets you work offline and use tools like a code editor and terminal. It gives you a full copy of the codebase where you can build, test, and commit changes locally before pushing them back to GitLab.

                1. Go to your repository and click on the button **code** (Its on the upper left corner ;)
                2. Copy the SSH code
                3.  In your terminal,go to the directory where you want to have your repo and run:
  ```bash
    git clone {{PASTEssh}}
```
                4. You can now access your cloned repo as to any folder in your computer, using cd.
                5. Add your user name to the computer.
                ```bash
                git config --global user.name your name
                ```
                6. Add your user email to the computer.
                 ```bash
                $ git config --global user.email your email
                ```

## 3️⃣ Create a New Branch for Each Edit
**Why do we always have to create a new branch?**
Working on separate branches for each task:
        - Keeps the main branch clean and stable
        - Helps organize changes by purpose
        - Makes it easier to review, test, and revert individual features
        - Prevents conflicts when multiple people are working in parallel
        - Each branch becomes a self-contained unit of work.
To create a new branch, go to your terminal and run:
  ```bash
    git checkout -b myNewBranch
```
Note that when you create a new branch, it copies the one you are currently on.
## CONGRATULATIONS, YOU ARE NOW READY TO START WORKING

## 4️⃣ Make Commits and Push Your Code
After each small, meaningful change to your code, you should be making a commit.
``` bash
git add .
git commit -m "Explain clearly what was changed"
git push origin your-branch-name
```
## 5️⃣ Create a Merge Request (MR)
Once you've pushed your branch:
        1. Go to GitLab → click "Create merge request"
        2. Fill in:
                A clear title
                A descriptive message (what changed & why it needed to be changed, some context on the new feature , how to test, Demos, images, anything)
        3. Assign at least one reviewer
        4. Do not merge without approval
If approved, you (the author) must do the merge
🛑 Even if you’re the reviewer on someone else’s MR, don’t merge their code.

## Good practices for Merge Requests (MRs)
✅ One clear goal per MR
Don’t mix unrelated changes — one MR = one purpose.

✅ Small, frequent commits
Make it easier to track and revert if needed.

✅ Descriptive commit messages
Write messages that explain the what and why, e.g.:
Fix: prevent crash when username is missing

✅ Write a clear MR description
Explain what you did, why it matters, and any context needed for the reviewer.

✅ Assign a reviewer
Always assign someone to review before merging. Never self-merge without review.

✅ Let the author merge
Even if you reviewed it, the person who created the MR should be the one merging it — this avoids confusion and maintains responsibility.

✅ Keep discussion respectful and constructive
Reviews are a collaborative process — we're all working toward the same goal. 💬🤝

---
## Docker Deploy

Ver [Docker-deploy.md](./Docker-deploy.md) para más información

---
### Raspberry Pi Configs:
NOTE: BOTH THE RASPY AND THE LOCALDEV HAS TO BE ON THE SAME NETWORK TO WORK.
1. If you are using a hotspot, you have to deactivate the proxy settings, for that, you can do the following commands (this will only deactivate the settings for the living terminal):
```shell
unset http_proxy
unset https_proxy
unset ftp_proxy
unset HTTP_PROXY
unset HTTPS_PROXY
unset FTP_PROXY
```
2. Get your computer network IP (not from the raspy):
```shell
ip addr
```
check for #3, under the name " wlp3s0", use the ip: named under "inet" (until the /202) and add the port:
8080 for the website, 3306 to interact with the db

3. Do the following command to check for the active localdev:
```shell
curl inet ip
```
IP priv Gabi: 172.22.144.1
