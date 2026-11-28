"""More sample tables for the extra templates (columns are real Steampipe columns; a test checks that)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


def _ago(days: float = 0, hours: float = 0) -> str:
    return (datetime.now(UTC) - timedelta(days=days, hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ahead(days: float) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


A1, A2 = "111111111111", "222222222222"
ENC = {"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}

EXTRA: dict[str, list[dict[str, Any]]] = {
    "aws_s3_bucket": [
        {"name": "acme-public-assets", "arn": "arn:aws:s3:::acme-public-assets", "region": "us-east-1", "account_id": A1, "creation_date": _ago(400),
         "bucket_policy_is_public": True, "block_public_policy": False, "block_public_acls": False, "versioning_enabled": False, "server_side_encryption_configuration": ENC, "tags": {"Owner": "alice@example.com"}},
        {"name": "acme-customer-exports", "arn": "arn:aws:s3:::acme-customer-exports", "region": "eu-west-1", "account_id": A1, "creation_date": _ago(200),
         "bucket_policy_is_public": True, "block_public_policy": False, "block_public_acls": True, "versioning_enabled": True, "server_side_encryption_configuration": None, "tags": {}},
        {"name": "acme-logs-prod", "arn": "arn:aws:s3:::acme-logs-prod", "region": "us-east-1", "account_id": A2, "creation_date": _ago(700),
         "bucket_policy_is_public": False, "block_public_policy": True, "block_public_acls": True, "versioning_enabled": False, "server_side_encryption_configuration": ENC, "tags": {"Owner": "bob@example.com"}},
        {"name": "acme-backups", "arn": "arn:aws:s3:::acme-backups", "region": "us-west-2", "account_id": A2, "creation_date": _ago(900),
         "bucket_policy_is_public": False, "block_public_policy": True, "block_public_acls": True, "versioning_enabled": True, "server_side_encryption_configuration": ENC, "tags": {"Owner": "carol@example.com"}},
        {"name": "acme-scratch", "arn": "arn:aws:s3:::acme-scratch", "region": "us-east-1", "account_id": A2, "creation_date": _ago(60),
         "bucket_policy_is_public": False, "block_public_policy": True, "block_public_acls": True, "versioning_enabled": False, "server_side_encryption_configuration": None, "tags": {}},
    ],
    "aws_iam_user": [
        {"name": "alice", "user_id": "AIDA000000000000ALICE", "arn": f"arn:aws:iam::{A1}:user/alice", "account_id": A1, "create_date": _ago(700), "password_last_used": _ago(2), "mfa_enabled": True, "tags": {}},
        {"name": "bob", "user_id": "AIDA00000000000000BOB", "arn": f"arn:aws:iam::{A1}:user/bob", "account_id": A1, "create_date": _ago(500), "password_last_used": _ago(10), "mfa_enabled": False, "tags": {}},
        {"name": "carol", "user_id": "AIDA0000000000CAROL", "arn": f"arn:aws:iam::{A1}:user/carol", "account_id": A1, "create_date": _ago(300), "password_last_used": _ago(1), "mfa_enabled": False, "tags": {}},
        {"name": "ci-deployer", "user_id": "AIDA00000000000000CI1", "arn": f"arn:aws:iam::{A2}:user/ci-deployer", "account_id": A2, "create_date": _ago(900), "password_last_used": None, "mfa_enabled": False, "tags": {}},
        {"name": "dave", "user_id": "AIDA000000000000DAVE", "arn": f"arn:aws:iam::{A2}:user/dave", "account_id": A2, "create_date": _ago(100), "password_last_used": _ago(120), "mfa_enabled": True, "tags": {}},
    ],
    "aws_iam_access_key": [
        {"access_key_id": "AKIA000000000000AAA1", "user_name": "alice", "status": "Active", "create_date": _ago(30), "access_key_last_used_date": _ago(1), "account_id": A1},
        {"access_key_id": "AKIA000000000000BBB2", "user_name": "bob", "status": "Active", "create_date": _ago(200), "access_key_last_used_date": _ago(5), "account_id": A1},
        {"access_key_id": "AKIA000000000000CCC3", "user_name": "ci-deployer", "status": "Active", "create_date": _ago(640), "access_key_last_used_date": _ago(0.1), "account_id": A2},
        {"access_key_id": "AKIA000000000000DDD4", "user_name": "carol", "status": "Active", "create_date": _ago(120), "access_key_last_used_date": None, "account_id": A1},
        {"access_key_id": "AKIA000000000000FFF6", "user_name": "erin", "status": "Active", "create_date": _ago(hours=6), "access_key_last_used_date": None, "account_id": A1},
        {"access_key_id": "AKIA000000000000EEE5", "user_name": "dave", "status": "Inactive", "create_date": _ago(400), "access_key_last_used_date": _ago(300), "account_id": A2},
    ],
    "aws_rds_db_instance": [
        {"db_instance_identifier": "orders-prod", "arn": f"arn:aws:rds:us-east-1:{A1}:db:orders-prod", "region": "us-east-1", "account_id": A1, "engine": "postgres", "status": "available", "class": "db.r6g.large",
         "publicly_accessible": False, "storage_encrypted": True, "backup_retention_period": 7, "multi_az": True, "deletion_protection": True, "tags": {"Owner": "alice@example.com"}},
        {"db_instance_identifier": "legacy-reports", "arn": f"arn:aws:rds:us-east-1:{A1}:db:legacy-reports", "region": "us-east-1", "account_id": A1, "engine": "mysql", "status": "available", "class": "db.m5.large",
         "publicly_accessible": True, "storage_encrypted": False, "backup_retention_period": 0, "multi_az": False, "deletion_protection": False, "tags": {}},
        {"db_instance_identifier": "staging-db", "arn": f"arn:aws:rds:eu-west-1:{A2}:db:staging-db", "region": "eu-west-1", "account_id": A2, "engine": "postgres", "status": "available", "class": "db.t3.medium",
         "publicly_accessible": True, "storage_encrypted": True, "backup_retention_period": 1, "multi_az": False, "deletion_protection": False, "tags": {"Environment": "staging"}},
        {"db_instance_identifier": "analytics", "arn": f"arn:aws:rds:us-west-2:{A2}:db:analytics", "region": "us-west-2", "account_id": A2, "engine": "postgres", "status": "available", "class": "db.r5.xlarge",
         "publicly_accessible": False, "storage_encrypted": False, "backup_retention_period": 0, "multi_az": False, "deletion_protection": False, "tags": {"Owner": "carol@example.com"}},
    ],
    "aws_ebs_snapshot": [
        {"snapshot_id": f"snap-0000000000000000{i}", "arn": f"arn:aws:ec2:us-east-1:{A2}:snapshot/snap-0000000000000000{i}", "region": "us-east-1", "account_id": A2,
         "volume_id": f"vol-0000000000000000{i}", "volume_size": 50 + 10 * i, "state": "completed", "encrypted": i % 3 != 0, "start_time": _ago(d),
         "description": f"nightly backup {i}", "tags": {"Owner": "bob@example.com"} if i % 2 else {}}
        for i, d in enumerate([10, 45, 95, 130, 200, 260, 330, 410])
    ],
    "aws_vpc_security_group_rule": [
        {"security_group_rule_id": "sgr-00000001", "group_id": "sg-0aaa0001", "region": "us-east-1", "account_id": A1, "is_egress": False, "ip_protocol": "tcp", "from_port": 22, "to_port": 22, "cidr_ipv4": "0.0.0.0/0", "description": "ssh from anywhere"},
        {"security_group_rule_id": "sgr-00000002", "group_id": "sg-0aaa0002", "region": "us-east-1", "account_id": A1, "is_egress": False, "ip_protocol": "tcp", "from_port": 3389, "to_port": 3389, "cidr_ipv4": "0.0.0.0/0", "description": "rdp"},
        {"security_group_rule_id": "sgr-00000003", "group_id": "sg-0aaa0003", "region": "eu-west-1", "account_id": A2, "is_egress": False, "ip_protocol": "tcp", "from_port": 443, "to_port": 443, "cidr_ipv4": "0.0.0.0/0", "description": "https"},
        {"security_group_rule_id": "sgr-00000004", "group_id": "sg-0aaa0004", "region": "eu-west-1", "account_id": A2, "is_egress": False, "ip_protocol": "tcp", "from_port": 22, "to_port": 22, "cidr_ipv4": "10.0.0.0/8", "description": "ssh from the VPN"},
        {"security_group_rule_id": "sgr-00000005", "group_id": "sg-0aaa0005", "region": "us-west-2", "account_id": A2, "is_egress": False, "ip_protocol": "tcp", "from_port": 22, "to_port": 22, "cidr_ipv4": "0.0.0.0/0", "description": "ssh (temporary)"},
        {"security_group_rule_id": "sgr-00000006", "group_id": "sg-0aaa0001", "region": "us-east-1", "account_id": A1, "is_egress": True, "ip_protocol": "-1", "from_port": None, "to_port": None, "cidr_ipv4": "0.0.0.0/0", "description": "all outbound"},
    ],
    "aws_lambda_function": [
        {"name": "invoice-pdf", "arn": f"arn:aws:lambda:us-east-1:{A1}:function:invoice-pdf", "region": "us-east-1", "account_id": A1, "runtime": "python3.7", "last_modified": _ago(500), "memory_size": 256, "tags": {"Owner": "alice@example.com"}},
        {"name": "image-resize", "arn": f"arn:aws:lambda:us-east-1:{A1}:function:image-resize", "region": "us-east-1", "account_id": A1, "runtime": "nodejs14.x", "last_modified": _ago(420), "memory_size": 512, "tags": {}},
        {"name": "slack-notifier", "arn": f"arn:aws:lambda:eu-west-1:{A2}:function:slack-notifier", "region": "eu-west-1", "account_id": A2, "runtime": "python3.12", "last_modified": _ago(20), "memory_size": 128, "tags": {"Owner": "bob@example.com"}},
        {"name": "nightly-report", "arn": f"arn:aws:lambda:eu-west-1:{A2}:function:nightly-report", "region": "eu-west-1", "account_id": A2, "runtime": "python3.8", "last_modified": _ago(380), "memory_size": 1024, "tags": {}},
        {"name": "webhook-ingest", "arn": f"arn:aws:lambda:us-west-2:{A2}:function:webhook-ingest", "region": "us-west-2", "account_id": A2, "runtime": "nodejs20.x", "last_modified": _ago(8), "memory_size": 256, "tags": {"Owner": "carol@example.com"}},
    ],
    "aws_acm_certificate": [
        {"certificate_arn": f"arn:aws:acm:us-east-1:{A1}:certificate/c1", "domain_name": "www.example.com", "region": "us-east-1", "account_id": A1, "status": "ISSUED", "not_after": _ahead(9), "in_use_by": ["lb-1"]},
        {"certificate_arn": f"arn:aws:acm:us-east-1:{A1}:certificate/c2", "domain_name": "api.example.com", "region": "us-east-1", "account_id": A1, "status": "ISSUED", "not_after": _ahead(24), "in_use_by": ["lb-2"]},
        {"certificate_arn": f"arn:aws:acm:eu-west-1:{A2}:certificate/c3", "domain_name": "shop.example.com", "region": "eu-west-1", "account_id": A2, "status": "ISSUED", "not_after": _ahead(200), "in_use_by": []},
        {"certificate_arn": f"arn:aws:acm:eu-west-1:{A2}:certificate/c4", "domain_name": "old.example.com", "region": "eu-west-1", "account_id": A2, "status": "EXPIRED", "not_after": _ago(12), "in_use_by": []},
    ],
    "aws_cloudwatch_alarm": [
        {"name": "orders-5xx-high", "arn": f"arn:aws:cloudwatch:us-east-1:{A1}:alarm:orders-5xx-high", "region": "us-east-1", "account_id": A1, "state_value": "ALARM", "state_reason": "Threshold Crossed: 5xx count 82 > 50", "metric_name": "HTTPCode_Target_5XX_Count", "namespace": "AWS/ApplicationELB", "state_updated_timestamp": _ago(hours=1)},
        {"name": "db-cpu-high", "arn": f"arn:aws:cloudwatch:us-east-1:{A1}:alarm:db-cpu-high", "region": "us-east-1", "account_id": A1, "state_value": "ALARM", "state_reason": "Threshold Crossed: CPU 94% > 85%", "metric_name": "CPUUtilization", "namespace": "AWS/RDS", "state_updated_timestamp": _ago(hours=3)},
        {"name": "queue-depth", "arn": f"arn:aws:cloudwatch:eu-west-1:{A2}:alarm:queue-depth", "region": "eu-west-1", "account_id": A2, "state_value": "OK", "state_reason": "Threshold not crossed", "metric_name": "ApproximateNumberOfMessagesVisible", "namespace": "AWS/SQS", "state_updated_timestamp": _ago(hours=9)},
        {"name": "disk-low", "arn": f"arn:aws:cloudwatch:eu-west-1:{A2}:alarm:disk-low", "region": "eu-west-1", "account_id": A2, "state_value": "ALARM", "state_reason": "Threshold Crossed: free disk 4% < 10%", "metric_name": "disk_free_percent", "namespace": "CWAgent", "state_updated_timestamp": _ago(hours=30)},
        {"name": "latency-p99", "arn": f"arn:aws:cloudwatch:us-west-2:{A2}:alarm:latency-p99", "region": "us-west-2", "account_id": A2, "state_value": "INSUFFICIENT_DATA", "state_reason": "No data", "metric_name": "Latency", "namespace": "AWS/ApplicationELB", "state_updated_timestamp": _ago(hours=5)},
    ],
    "aws_vpc_nat_gateway": [
        {"nat_gateway_id": "nat-0000000000000001", "region": "us-east-1", "account_id": A1, "state": "available", "create_time": _ago(300), "vpc_id": "vpc-0001", "tags": {"Environment": "prod"}},
        {"nat_gateway_id": "nat-0000000000000002", "region": "us-east-1", "account_id": A1, "state": "available", "create_time": _ago(120), "vpc_id": "vpc-0002", "tags": {"Environment": "dev"}},
        {"nat_gateway_id": "nat-0000000000000003", "region": "eu-west-1", "account_id": A2, "state": "available", "create_time": _ago(45), "vpc_id": "vpc-0003", "tags": {"Environment": "staging"}},
        {"nat_gateway_id": "nat-0000000000000004", "region": "eu-west-1", "account_id": A2, "state": "failed", "create_time": _ago(3), "vpc_id": "vpc-0003", "tags": {}},
    ],
    "aws_kms_key": [
        {"id": "key-0001", "arn": f"arn:aws:kms:us-east-1:{A1}:key/key-0001", "region": "us-east-1", "account_id": A1, "key_manager": "CUSTOMER", "key_state": "Enabled", "key_rotation_enabled": False, "creation_date": _ago(500), "description": "orders database"},
        {"id": "key-0002", "arn": f"arn:aws:kms:us-east-1:{A1}:key/key-0002", "region": "us-east-1", "account_id": A1, "key_manager": "CUSTOMER", "key_state": "Enabled", "key_rotation_enabled": True, "creation_date": _ago(400), "description": "s3 exports"},
        {"id": "key-0003", "arn": f"arn:aws:kms:eu-west-1:{A2}:key/key-0003", "region": "eu-west-1", "account_id": A2, "key_manager": "CUSTOMER", "key_state": "Enabled", "key_rotation_enabled": False, "creation_date": _ago(250), "description": "ci secrets"},
        {"id": "key-0004", "arn": f"arn:aws:kms:eu-west-1:{A2}:key/key-0004", "region": "eu-west-1", "account_id": A2, "key_manager": "AWS", "key_state": "Enabled", "key_rotation_enabled": False, "creation_date": _ago(900), "description": "AWS managed"},
    ],
    "aws_s3_object": [
        {"key": "reports/2026-11/revenue.csv", "bucket_name": "acme-customer-exports", "region": "eu-west-1", "last_modified": _ago(hours=0.1), "content_length": 482113, "content_type": "text/csv", "storage_class": "STANDARD"},
        {"key": "reports/2026-11/churn.xlsx", "bucket_name": "acme-customer-exports", "region": "eu-west-1", "last_modified": _ago(hours=0.2), "content_length": 91422, "content_type": "application/vnd.ms-excel", "storage_class": "STANDARD"},
        {"key": "reports/2026-10/revenue.csv", "bucket_name": "acme-customer-exports", "region": "eu-west-1", "last_modified": _ago(days=30), "content_length": 455001, "content_type": "text/csv", "storage_class": "STANDARD"},
    ],
    "gitlab_merge_request": [
        {"id": 9001, "iid": 14, "project_id": 42, "title": "Add retry to payment webhook", "state": "opened", "created_at": _ago(25), "updated_at": _ago(21), "author_username": "alice", "source_branch": "feat/retry", "target_branch": "main", "draft": False, "web_url": "https://gitlab.example.com/acme/shop/-/merge_requests/14"},
        {"id": 9002, "iid": 15, "project_id": 42, "title": "Upgrade Postgres driver", "state": "opened", "created_at": _ago(18), "updated_at": _ago(16), "author_username": "bob", "source_branch": "chore/pg", "target_branch": "main", "draft": False, "web_url": "https://gitlab.example.com/acme/shop/-/merge_requests/15"},
        {"id": 9003, "iid": 16, "project_id": 42, "title": "WIP: new checkout", "state": "opened", "created_at": _ago(40), "updated_at": _ago(30), "author_username": "carol", "source_branch": "feat/checkout", "target_branch": "main", "draft": True, "web_url": "https://gitlab.example.com/acme/shop/-/merge_requests/16"},
        {"id": 9004, "iid": 17, "project_id": 42, "title": "Fix typo in README", "state": "opened", "created_at": _ago(2), "updated_at": _ago(1), "author_username": "dave", "source_branch": "docs/typo", "target_branch": "main", "draft": False, "web_url": "https://gitlab.example.com/acme/shop/-/merge_requests/17"},
        {"id": 9005, "iid": 18, "project_id": 42, "title": "Merged last week", "state": "merged", "created_at": _ago(9), "updated_at": _ago(7), "author_username": "alice", "source_branch": "feat/x", "target_branch": "main", "draft": False, "web_url": "https://gitlab.example.com/acme/shop/-/merge_requests/18"},
    ],
    "gitlab_project": [
        {"id": 42, "name": "shop", "full_path": "acme/shop", "visibility": "private", "last_activity_at": _ago(1), "archived": False, "web_url": "https://gitlab.example.com/acme/shop", "open_issues_count": 12},
        {"id": 43, "name": "legacy-admin", "full_path": "acme/legacy-admin", "visibility": "private", "last_activity_at": _ago(420), "archived": False, "web_url": "https://gitlab.example.com/acme/legacy-admin", "open_issues_count": 3},
        {"id": 44, "name": "hackday-2023", "full_path": "acme/hackday-2023", "visibility": "public", "last_activity_at": _ago(700), "archived": False, "web_url": "https://gitlab.example.com/acme/hackday-2023", "open_issues_count": 0},
        {"id": 45, "name": "infra", "full_path": "acme/infra", "visibility": "internal", "last_activity_at": _ago(3), "archived": False, "web_url": "https://gitlab.example.com/acme/infra", "open_issues_count": 7},
    ],
}

JIRA_EXTRA = [  # type, updated, duedate, status_category for the four existing jira_issue rows, in order
    ("Task", _ago(2), _ahead(5), "To Do"), ("Task", _ago(45), _ago(10), "In Progress"),
    ("Bug", _ago(1), None, "In Progress"), ("Task", _ago(60), _ago(20), "To Do"),
]


def extend(tables: dict[str, list[dict[str, Any]]]) -> None:
    tables.update(EXTRA)
    tables["gitlab_project_deployment"].append(  # recent, so "last 24 hours" templates have something to find
        {"id": "504", "project_id": "42", "status": "failed", "environment_name": "production", "ref": "release-2026-11", "sha": "0000000000000000000000000000000000000004",
         "created_at": _ago(hours=3), "updated_at": _ago(hours=3)})
    for row, (typ, upd, due, cat) in zip(tables["jira_issue"], JIRA_EXTRA, strict=False):
        row.update({"type": typ, "updated": upd, "duedate": due, "status_category": cat})
