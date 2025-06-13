
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

## 2️⃣ Fork the Repository
**Why Fork a repository?**
Forking creates your own copy of the repository under your GitLab account, allowing you to freely make changes without affecting the original project. It’s the starting point for contributing in a safe and isolated way.

                1. Go to the main repo on GitLab.
                2. Click "Fork" (top-right).
                3. Choose your namespace (usually your account).

## 3️⃣ Clone the Forked Repo
**Why Clone a repository?**
Cloning the repo to your local machine lets you work offline and use tools like a code editor and terminal. It gives you a full copy of the codebase where you can build, test, and commit changes locally before pushing them back to GitLab.

                1. Go to your forked repository and click on **code**
                2. Copy the SSH code
                3.  In your terminal,go to the directory where you want to have your repo and run:
  ```bash
    git clone {{ssh}}
```      
                4. You can now access your cloned repo as to any folder in your computer, using cd.
## 4️⃣ Create a New Branch for Each Edit
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

## 5️⃣ Make Commits and Push Your Code
After each small, meaningful change to your code, you should be making a commit.
``` bash
git add .
git commit -m "Explain clearly what was changed"
git push origin your-branch-name
```
## 6️⃣ Create a Merge Request (MR)
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
