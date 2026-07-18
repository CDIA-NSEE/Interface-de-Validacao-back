# GitHub Actions CI/CD Setup

## Required AWS Resources

### 1. IAM Role for GitHub Actions
Create an IAM role `GitHubActionsDeployRole` with trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:your-org/Interface-de-Validacao-back:*"
        }
      }
    }
  ]
}
```

### 2. Required IAM Permissions
Attach these policies to the role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:UpdateFunctionCode",
        "lambda:PublishVersion",
        "lambda:UpdateAlias",
        "lambda:GetFunction"
      ],
      "Resource": "arn:aws:lambda:us-east-1:${AWS_ACCOUNT_ID}:function:validacao-staging-backend"
    }
  ]
}
```

### 3. GitHub Secrets
Add these secrets to the repository:

| Secret | Value |
|--------|-------|
| `AWS_ACCOUNT_ID` | Your 12-digit AWS account ID |
| `AWS_ROLE_ARN` | ARN of the `GitHubActionsDeployRole` |

### 4. ECR Repository
Ensure ECR repository exists:
```bash
aws ecr create-repository --repository-name bp-ecg-validacao-backend --region us-east-1
```

### 5. Lambda Function
Ensure Lambda function exists (created by Terraform):
- Name: `validacao-staging-backend` (staging) / `validacao-prod-backend` (prod)
- Package type: Image
- Architecture: arm64

## Workflow Triggers
- **Push to main/feat/deploy-ci-cd**: Runs tests, builds, pushes to ECR, updates Lambda
- **Pull Request to main**: Runs tests only

## Local Testing
```bash
# Run tests locally
cd Interface-de-Validacao-back
python -m pytest tests/ -v --cov=app --cov-fail-under=80

# Type check
pyrefly check app/

# Lint
ruff check app/
```