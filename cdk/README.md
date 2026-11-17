# CDK app: one stack per lab

```bash
npm ci
npx cdk bootstrap                 # once per account and Region
npx cdk list                      # Lab01StaticSite ... Lab08AiBedrock
npx cdk diff   Lab03ApiDynamoDb   # what would change
npx cdk deploy Lab03ApiDynamoDb   # deploy ONE lab at a time, never --all
npx cdk destroy Lab03ApiDynamoDb
```

| Stack | Context you can pass |
|-------|----------------------|
| `Lab04EventTriggers` | `-c email=you@example.com` |
| `Lab05LambdaRds` | run `npm ci --omit=dev` in `labs/05-lambda-rds/src` first |
| `Lab06Ec2Website` | `-c repoUrl=https://github.com/you/aws-foundations-labs.git` |
| `Lab07Capstone` | `-c stage=1`, `2` or `3` |
| `Lab08AiBedrock` | `-c modelId=eu.amazon.nova-micro-v1:0 -c siteContext="..."` |

Shared defaults for every function (Node.js 22, arm64, 7-day logs) live in `lib/shared.ts`.
