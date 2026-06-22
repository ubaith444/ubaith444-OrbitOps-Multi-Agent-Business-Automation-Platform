# AWS infrastructure contract

Provision production resources with Terraform or AWS CDK in a dedicated infrastructure repository/state backend:

- VPC with public load-balancer subnets and private application/data subnets in 2–3 availability zones
- WAF + ALB, ECS services (web/API/worker), ECR repositories and autoscaling policies
- RDS PostgreSQL Multi-AZ, ElastiCache Redis, S3 report bucket, KMS keys
- Secrets Manager values, least-privilege task roles, CloudWatch log groups/alarms
- Route 53/ACM and VPC endpoints for ECR, S3, Secrets Manager, and CloudWatch

Keep application and infrastructure changes reviewable but independently deployable. Pin providers, lock state with DynamoDB/S3, run plan on pull requests, and require approval to apply production.

