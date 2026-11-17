# Lab 00 · Setup: a safe account and your tools

> Do this once. It protects your account and your money, and installs what every other lab needs.
> Time: 30 minutes · Cost: $0

## 1. Account safety (console)

1. **Free plan account:** sign up at [aws.amazon.com/free](https://aws.amazon.com/free) and choose the **Free plan**. It cannot charge your card.
2. **MFA on the root user:** account name (top right) → **Security credentials** → **Assign MFA device** → authenticator app.
3. **Budget alert:** search **Budgets** → **Create budget** → **Use a template** → **Zero spend budget** → your email → **Create**. (This also earns $20 in credits.)
4. **Pick one Region** with the menu at the top right and use it in every lab. Newer Regions such as Tel Aviv (`il-central-1`) must first be enabled under **Manage Regions**.
5. **Stop using root:** open **IAM Identity Center** → **Enable** → create a user for yourself with the `AdministratorAccess` permission set, and sign in with that user from now on.

## 2. Tools on your laptop

| Tool | Check | Install |
|------|-------|---------|
| AWS CLI v2 (2.35+) | `aws --version` | [docs.aws.amazon.com/cli](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| Python 3.11+ (3.13 recommended) | `python3 --version` | [python.org](https://www.python.org/downloads/) |
| Node.js 22 (only to run the `cdk` command) | `node --version` | [nodejs.org](https://nodejs.org) |
| Git | `git --version` | [git-scm.com](https://git-scm.com) |

## 3. Sign in from the terminal, safely

```bash
aws login                                  # opens the browser, gives short-lived credentials
aws configure set region eu-central-1      # your course Region
aws sts get-caller-identity                # which account and user you are
```

`aws login` credentials expire on their own: there are no access keys to leak.
If a tool later says it can't find credentials, run this in that terminal:

```bash
eval "$(aws configure export-credentials --format env)"
```

## 4. Get the labs and prepare the CDK

```bash
git clone https://github.com/<you>/AWS-Workshop.git   # your fork of github.com/mkabajah/AWS-Workshop
cd AWS-Workshop
python -m venv .venv            # a private Python environment for this project
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest                          # runs the Lambda unit tests locally, no AWS needed

cd cdk
pip install -r requirements.txt # the CDK library for Python
npm install                     # the cdk command
npx cdk bootstrap               # once per account and Region: a small stack the CDK uses to deploy
npx cdk list                    # shows Lab01StaticSite ... Lab08AiBedrock
```

## 5. Your AI coding agent (optional, recommended)

```bash
aws configure agent-toolkit     # finds your agents, adds the AWS skills and the AWS MCP Server
```

Then ask your agent: *"Which AWS skills and tools can you use? Which account and Region would you deploy to?"*

## Fix it

| You see | Fix |
|---------|-----|
| `aws: command not found` | Install AWS CLI v2 and open a new terminal |
| `No module named pytest` / `boto3` | Activate the virtual environment: `source .venv/bin/activate` |
| `Unable to locate credentials` | `aws login` again (credentials expire) |
| `cdk bootstrap` fails with access denied | You're signed in as a user without admin rights; use your Identity Center admin user |
| Resources "disappear" in the console | You switched Region; switch back |
