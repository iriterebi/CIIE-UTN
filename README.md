
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
## Docker Deploy (dev)

Por ahora necesitamos dos shells

### First time using docker
1. Copy .env.example file, change the name to .env and complete it with your db data {Jesus always has the answer, amen}, DO THIS BOTH FOR YOUR .env IN DB AND IN WEB
2. Do this:
```shell
        docker network create ciie-test1
```

### Para la Db
```shell
cd Db && docker compose up
# o puedes corriendolo en segundo plano
cd Db && docker compose up -d

# si es primera vez que se corre la Db habrá que crear las tablas,
# para ello, es necesario correr el siguiente script (en la carpeta Db/)

./migrate.sh
```

### Para el PHP
```shell
cd Web && docker compose up
# o puedes corriendolo en segundo plano
cd Web && docker compose up -d
```
IF you get an error trying to build the web docker, run the following command and then try again...
```shell
docker pull php:8.2-apache-bookworm
```

y luego abrir http://localhost:8080 en el browser para ver la página

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

