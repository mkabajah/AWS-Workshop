# CDK app: one stack per lab, in Python

```bash
# from the repository root, with your virtual environment active
cd cdk
pip install -r requirements.txt   # aws-cdk-lib: the CDK library for Python
npm install                       # the cdk command itself (it runs on Node.js)

npx cdk bootstrap                 # once per account and Region
npx cdk list                      # Lab01StaticSite ... Lab08AiBedrock
npx cdk diff   Lab03ApiDynamoDb   # what would change
npx cdk deploy Lab03ApiDynamoDb   # deploy ONE lab at a time, never --all
npx cdk destroy Lab03ApiDynamoDb
```

| Stack | Context you can pass |
|-------|----------------------|
| `Lab04EventTriggers` | `-c email=you@example.com` |
| `Lab05LambdaRds` | run `python labs/05-lambda-rds/scripts/package.py` first |
| `Lab06Ec2Website` | `-c repoUrl=https://github.com/you/AWS-Workshop.git` |
| `Lab07Capstone` | `-c stage=1`, `2` or `3` |
| `Lab08AiBedrock` | `-c modelId=eu.amazon.nova-micro-v1:0 -c siteContext="..."` |

```
app.py              creates one stack per lab and reads the -c values
stacks/shared.py    LabFunction: Python 3.13, arm64, 7-day logs, used by every lab
stacks/lab0N_*.py   one file per lab
```

Why npm for a Python project? The `cdk` command-line tool is written in TypeScript and ships on npm.
Your stacks stay 100% Python; `npx cdk` just runs `python3 app.py` (see `cdk.json`).
