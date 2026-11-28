"""Sample rows for the demo database (generated once by the Phase 1 build; edit freely).

Columns are a subset of the real Steampipe tables of the same name; a test checks that against the catalog.
JSON columns hold Python lists/dicts (stored as JSON text in the SQLite demo database).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


def _ago(hours: float) -> str:
    """Timestamps relative to now, so 'last 7 days' style packs keep finding sample rows."""
    return (datetime.now(UTC) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


TABLES: dict[str, list[dict[str, Any]]] = {
    "aws_guardduty_finding": [
        {"id": "f0001", "arn": "arn:aws:guardduty:us-east-1:111111111111:detector/d1/finding/f0001", "title": "Unusual API calls from a Tor exit node", "type": "UnauthorizedAccess:IAMUser/TorIPCaller", "severity": 8.0,
         "region": "us-east-1", "account_id": "111111111111", "created_at": _ago(20)},
        {"id": "f0002", "arn": "arn:aws:guardduty:eu-west-1:222222222222:detector/d1/finding/f0002", "title": "EC2 instance communicating with a known C&C server", "type": "Backdoor:EC2/C&CActivity.B!DNS", "severity": 8.9,
         "region": "eu-west-1", "account_id": "222222222222", "created_at": _ago(50)},
        {"id": "f0003", "arn": "arn:aws:guardduty:us-east-1:111111111111:detector/d1/finding/f0003", "title": "S3 bucket policy allows public access", "type": "Policy:S3/BucketAnonymousAccessGranted", "severity": 7.0,
         "region": "us-east-1", "account_id": "111111111111", "created_at": _ago(100)},
        {"id": "f0004", "arn": "arn:aws:guardduty:us-east-1:222222222222:detector/d1/finding/f0004", "title": "Port scan from an internal instance", "type": "Recon:EC2/Portscan", "severity": 5.0,
         "region": "us-east-1", "account_id": "222222222222", "created_at": _ago(30)},
        {"id": "f0005", "arn": "arn:aws:guardduty:eu-west-1:111111111111:detector/d1/finding/f0005", "title": "Console login without MFA", "type": "Policy:IAMUser/RootCredentialUsage", "severity": 4.0,
         "region": "eu-west-1", "account_id": "111111111111", "created_at": _ago(60)},
        {"id": "f0006", "arn": "arn:aws:guardduty:us-east-1:111111111111:detector/d1/finding/f0006", "title": "Old high-severity finding (outside the window)", "type": "CryptoCurrency:EC2/BitcoinTool.B!DNS", "severity": 8.0,
         "region": "us-east-1", "account_id": "111111111111", "created_at": _ago(480)},
    ],
    "aws_ebs_volume": [
        {
            "volume_id": "vol-00000000000000001",
            "region": "us-east-1",
            "account_id": "222222222222",
            "volume_type": "gp3",
            "size": 50,
            "iops": 3000,
            "state": "in-use",
            "create_time": "2026-02-11T10:00:00Z",
            "attachments": [
                {
                    "InstanceId": "i-00000000000000001",
                    "Device": "/dev/xvda"
                }
            ],
            "tags": {
                "Environment": "staging",
                "Owner": "bob@example.com"
            }
        },
        {
            "volume_id": "vol-00000000000000002",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "volume_type": "io1",
            "size": 100,
            "iops": 6000,
            "state": "in-use",
            "create_time": "2026-03-12T10:00:00Z",
            "attachments": [
                {
                    "InstanceId": "i-00000000000000002",
                    "Device": "/dev/xvda"
                }
            ],
            "tags": {
                "Environment": "dev",
                "Owner": "carol@example.com"
            }
        },
        {
            "volume_id": "vol-00000000000000003",
            "region": "us-east-1",
            "account_id": "222222222222",
            "volume_type": "io2",
            "size": 500,
            "iops": 16000,
            "state": "available",
            "create_time": "2026-04-13T10:00:00Z",
            "attachments": [],
            "tags": {
                "Environment": "prod"
            }
        },
        {
            "volume_id": "vol-00000000000000004",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "volume_type": "gp2",
            "size": 1000,
            "iops": 3000,
            "state": "in-use",
            "create_time": "2026-05-14T10:00:00Z",
            "attachments": [
                {
                    "InstanceId": "i-00000000000000004",
                    "Device": "/dev/xvda"
                }
            ],
            "tags": {
                "Environment": "staging",
                "Owner": "alice@example.com"
            }
        },
        {
            "volume_id": "vol-00000000000000005",
            "region": "us-east-1",
            "account_id": "222222222222",
            "volume_type": "gp3",
            "size": 20,
            "iops": 3000,
            "state": "in-use",
            "create_time": "2026-06-15T10:00:00Z",
            "attachments": [
                {
                    "InstanceId": "i-00000000000000005",
                    "Device": "/dev/xvda"
                }
            ],
            "tags": {
                "Environment": "dev",
                "Owner": "bob@example.com"
            }
        },
        {
            "volume_id": "vol-00000000000000006",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "volume_type": "io1",
            "size": 50,
            "iops": 6000,
            "state": "available",
            "create_time": "2026-07-16T10:00:00Z",
            "attachments": [],
            "tags": {
                "Environment": "prod",
                "Owner": "carol@example.com"
            }
        },
        {
            "volume_id": "vol-00000000000000007",
            "region": "us-east-1",
            "account_id": "222222222222",
            "volume_type": "io2",
            "size": 100,
            "iops": 16000,
            "state": "in-use",
            "create_time": "2026-08-17T10:00:00Z",
            "attachments": [
                {
                    "InstanceId": "i-00000000000000007",
                    "Device": "/dev/xvda"
                }
            ],
            "tags": {
                "Environment": "staging"
            }
        },
        {
            "volume_id": "vol-00000000000000008",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "volume_type": "gp2",
            "size": 500,
            "iops": 3000,
            "state": "in-use",
            "create_time": "2026-09-18T10:00:00Z",
            "attachments": [
                {
                    "InstanceId": "i-00000000000000008",
                    "Device": "/dev/xvda"
                }
            ],
            "tags": {
                "Environment": "dev",
                "Owner": "alice@example.com"
            }
        },
        {
            "volume_id": "vol-00000000000000009",
            "region": "us-east-1",
            "account_id": "222222222222",
            "volume_type": "gp3",
            "size": 1000,
            "iops": 3000,
            "state": "available",
            "create_time": "2026-01-10T10:00:00Z",
            "attachments": [],
            "tags": {
                "Environment": "prod",
                "Owner": "bob@example.com"
            }
        },
        {
            "volume_id": "vol-0000000000000000a",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "volume_type": "io1",
            "size": 20,
            "iops": 6000,
            "state": "in-use",
            "create_time": "2026-02-11T10:00:00Z",
            "attachments": [
                {
                    "InstanceId": "i-0000000000000000a",
                    "Device": "/dev/xvda"
                }
            ],
            "tags": {
                "Environment": "staging",
                "Owner": "carol@example.com"
            }
        },
        {
            "volume_id": "vol-0000000000000000b",
            "region": "us-east-1",
            "account_id": "222222222222",
            "volume_type": "io2",
            "size": 50,
            "iops": 16000,
            "state": "in-use",
            "create_time": "2026-03-12T10:00:00Z",
            "attachments": [
                {
                    "InstanceId": "i-0000000000000000b",
                    "Device": "/dev/xvda"
                }
            ],
            "tags": {
                "Environment": "dev"
            }
        },
        {
            "volume_id": "vol-0000000000000000c",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "volume_type": "gp2",
            "size": 100,
            "iops": 3000,
            "state": "available",
            "create_time": "2026-04-13T10:00:00Z",
            "attachments": [],
            "tags": {
                "Environment": "prod",
                "Owner": "alice@example.com"
            }
        },
        {
            "volume_id": "vol-0000000000000000d",
            "region": "us-east-1",
            "account_id": "222222222222",
            "volume_type": "gp3",
            "size": 500,
            "iops": 3000,
            "state": "in-use",
            "create_time": "2026-05-14T10:00:00Z",
            "attachments": [
                {
                    "InstanceId": "i-0000000000000000d",
                    "Device": "/dev/xvda"
                }
            ],
            "tags": {
                "Environment": "staging",
                "Owner": "bob@example.com"
            }
        },
        {
            "volume_id": "vol-0000000000000000e",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "volume_type": "io1",
            "size": 1000,
            "iops": 6000,
            "state": "in-use",
            "create_time": "2026-06-15T10:00:00Z",
            "attachments": [
                {
                    "InstanceId": "i-0000000000000000e",
                    "Device": "/dev/xvda"
                }
            ],
            "tags": {
                "Environment": "dev",
                "Owner": "carol@example.com"
            }
        },
        {
            "volume_id": "vol-0000000000000000f",
            "region": "us-east-1",
            "account_id": "222222222222",
            "volume_type": "io2",
            "size": 20,
            "iops": 16000,
            "state": "available",
            "create_time": "2026-07-16T10:00:00Z",
            "attachments": [],
            "tags": {
                "Environment": "prod"
            }
        },
        {
            "volume_id": "vol-00000000000000010",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "volume_type": "gp2",
            "size": 50,
            "iops": 3000,
            "state": "in-use",
            "create_time": "2026-08-17T10:00:00Z",
            "attachments": [
                {
                    "InstanceId": "i-00000000000000010",
                    "Device": "/dev/xvda"
                }
            ],
            "tags": {
                "Environment": "staging",
                "Owner": "alice@example.com"
            }
        },
        {
            "volume_id": "vol-00000000000000011",
            "region": "us-east-1",
            "account_id": "222222222222",
            "volume_type": "gp3",
            "size": 100,
            "iops": 3000,
            "state": "in-use",
            "create_time": "2026-09-18T10:00:00Z",
            "attachments": [
                {
                    "InstanceId": "i-00000000000000011",
                    "Device": "/dev/xvda"
                }
            ],
            "tags": {
                "Environment": "dev",
                "Owner": "bob@example.com"
            }
        },
        {
            "volume_id": "vol-00000000000000012",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "volume_type": "io1",
            "size": 500,
            "iops": 6000,
            "state": "available",
            "create_time": "2026-01-10T10:00:00Z",
            "attachments": [],
            "tags": {
                "Environment": "prod",
                "Owner": "carol@example.com"
            }
        },
        {
            "volume_id": "vol-00000000000000013",
            "region": "us-east-1",
            "account_id": "222222222222",
            "volume_type": "io2",
            "size": 1000,
            "iops": 16000,
            "state": "in-use",
            "create_time": "2026-02-11T10:00:00Z",
            "attachments": [
                {
                    "InstanceId": "i-00000000000000013",
                    "Device": "/dev/xvda"
                }
            ],
            "tags": {
                "Environment": "staging"
            }
        },
        {
            "volume_id": "vol-00000000000000014",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "volume_type": "gp2",
            "size": 20,
            "iops": 3000,
            "state": "in-use",
            "create_time": "2026-03-12T10:00:00Z",
            "attachments": [
                {
                    "InstanceId": "i-00000000000000014",
                    "Device": "/dev/xvda"
                }
            ],
            "tags": {
                "Environment": "dev",
                "Owner": "alice@example.com"
            }
        },
        {
            "volume_id": "vol-00000000000000015",
            "region": "us-east-1",
            "account_id": "222222222222",
            "volume_type": "gp3",
            "size": 50,
            "iops": 3000,
            "state": "available",
            "create_time": "2026-04-13T10:00:00Z",
            "attachments": [],
            "tags": {
                "Environment": "prod",
                "Owner": "bob@example.com"
            }
        },
        {
            "volume_id": "vol-00000000000000016",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "volume_type": "io1",
            "size": 100,
            "iops": 6000,
            "state": "in-use",
            "create_time": "2026-05-14T10:00:00Z",
            "attachments": [
                {
                    "InstanceId": "i-00000000000000016",
                    "Device": "/dev/xvda"
                }
            ],
            "tags": {
                "Environment": "staging",
                "Owner": "carol@example.com"
            }
        },
        {
            "volume_id": "vol-00000000000000017",
            "region": "us-east-1",
            "account_id": "222222222222",
            "volume_type": "io2",
            "size": 500,
            "iops": 16000,
            "state": "in-use",
            "create_time": "2026-06-15T10:00:00Z",
            "attachments": [
                {
                    "InstanceId": "i-00000000000000017",
                    "Device": "/dev/xvda"
                }
            ],
            "tags": {
                "Environment": "dev"
            }
        },
        {
            "volume_id": "vol-00000000000000018",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "volume_type": "gp2",
            "size": 1000,
            "iops": 3000,
            "state": "available",
            "create_time": "2026-07-16T10:00:00Z",
            "attachments": [],
            "tags": {
                "Environment": "prod",
                "Owner": "alice@example.com"
            }
        }
    ],
    "aws_ec2_instance": [
        {
            "instance_id": "i-00000000000000001",
            "region": "us-east-1",
            "account_id": "222222222222",
            "arn": "arn:aws:ec2:us-east-1:222222222222:instance/i-00000000000000001",
            "instance_type": "m5.large",
            "instance_state": "running",
            "launch_time": "2026-02-02T08:30:00Z",
            "tags": {
                "Environment": "staging",
                "Owner": "bob@example.com"
            }
        },
        {
            "instance_id": "i-00000000000000002",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "arn": "arn:aws:ec2:eu-west-1:111111111111:instance/i-00000000000000002",
            "instance_type": "m5.2xlarge",
            "instance_state": "running",
            "launch_time": "2026-03-03T08:30:00Z",
            "tags": {
                "Environment": "prod",
                "Owner": "carol@example.com"
            }
        },
        {
            "instance_id": "i-00000000000000003",
            "region": "us-east-1",
            "account_id": "222222222222",
            "arn": "arn:aws:ec2:us-east-1:222222222222:instance/i-00000000000000003",
            "instance_type": "c5.xlarge",
            "instance_state": "running",
            "launch_time": "2026-04-04T08:30:00Z",
            "tags": {
                "Environment": "staging",
                "Owner": "alice@example.com"
            }
        },
        {
            "instance_id": "i-00000000000000004",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "arn": "arn:aws:ec2:eu-west-1:111111111111:instance/i-00000000000000004",
            "instance_type": "t3.micro",
            "instance_state": "running",
            "launch_time": "2026-05-05T08:30:00Z",
            "tags": {
                "Environment": "prod"
            }
        },
        {
            "instance_id": "i-00000000000000005",
            "region": "us-east-1",
            "account_id": "222222222222",
            "arn": "arn:aws:ec2:us-east-1:222222222222:instance/i-00000000000000005",
            "instance_type": "m5.large",
            "instance_state": "stopped",
            "launch_time": "2026-06-06T08:30:00Z",
            "tags": {
                "Environment": "staging",
                "Owner": "carol@example.com"
            }
        },
        {
            "instance_id": "i-00000000000000006",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "arn": "arn:aws:ec2:eu-west-1:111111111111:instance/i-00000000000000006",
            "instance_type": "m5.2xlarge",
            "instance_state": "running",
            "launch_time": "2026-07-07T08:30:00Z",
            "tags": {
                "Environment": "prod",
                "Owner": "alice@example.com"
            }
        },
        {
            "instance_id": "i-00000000000000007",
            "region": "us-east-1",
            "account_id": "222222222222",
            "arn": "arn:aws:ec2:us-east-1:222222222222:instance/i-00000000000000007",
            "instance_type": "c5.xlarge",
            "instance_state": "running",
            "launch_time": "2026-08-08T08:30:00Z",
            "tags": {
                "Environment": "staging",
                "Owner": "bob@example.com"
            }
        },
        {
            "instance_id": "i-00000000000000008",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "arn": "arn:aws:ec2:eu-west-1:111111111111:instance/i-00000000000000008",
            "instance_type": "t3.micro",
            "instance_state": "running",
            "launch_time": "2026-01-01T08:30:00Z",
            "tags": {
                "Environment": "prod"
            }
        },
        {
            "instance_id": "i-00000000000000009",
            "region": "us-east-1",
            "account_id": "222222222222",
            "arn": "arn:aws:ec2:us-east-1:222222222222:instance/i-00000000000000009",
            "instance_type": "m5.large",
            "instance_state": "running",
            "launch_time": "2026-02-02T08:30:00Z",
            "tags": {
                "Environment": "staging",
                "Owner": "alice@example.com"
            }
        },
        {
            "instance_id": "i-0000000000000000a",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "arn": "arn:aws:ec2:eu-west-1:111111111111:instance/i-0000000000000000a",
            "instance_type": "m5.2xlarge",
            "instance_state": "stopped",
            "launch_time": "2026-03-03T08:30:00Z",
            "tags": {
                "Environment": "prod",
                "Owner": "bob@example.com"
            }
        }
    ],
    "aws_vpc_eip": [
        {
            "allocation_id": "eipalloc-00000001",
            "public_ip": "203.0.113.1",
            "region": "us-east-1",
            "account_id": "222222222222",
            "association_id": None,
            "instance_id": None,
            "tags": {
                "Owner": "bob@example.com"
            }
        },
        {
            "allocation_id": "eipalloc-00000002",
            "public_ip": "203.0.113.2",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "association_id": "eipassoc-00000002",
            "instance_id": "i-00000000000000002",
            "tags": {
                "Owner": "carol@example.com"
            }
        },
        {
            "allocation_id": "eipalloc-00000003",
            "public_ip": "203.0.113.3",
            "region": "us-east-1",
            "account_id": "222222222222",
            "association_id": None,
            "instance_id": None,
            "tags": {
                "Owner": "alice@example.com"
            }
        },
        {
            "allocation_id": "eipalloc-00000004",
            "public_ip": "203.0.113.4",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "association_id": "eipassoc-00000004",
            "instance_id": "i-00000000000000004",
            "tags": {
                "Owner": "bob@example.com"
            }
        },
        {
            "allocation_id": "eipalloc-00000005",
            "public_ip": "203.0.113.5",
            "region": "us-east-1",
            "account_id": "222222222222",
            "association_id": None,
            "instance_id": None,
            "tags": {
                "Owner": "carol@example.com"
            }
        },
        {
            "allocation_id": "eipalloc-00000006",
            "public_ip": "203.0.113.6",
            "region": "eu-west-1",
            "account_id": "111111111111",
            "association_id": "eipassoc-00000006",
            "instance_id": "i-00000000000000006",
            "tags": {
                "Owner": "alice@example.com"
            }
        }
    ],
    "jira_issue": [
        {
            "id": "10000",
            "key": "OPS-100",
            "project_key": "OPS",
            "summary": "Unattached volumes in eu-west-1",
            "status": "To Do",
            "priority": "Medium",
            "assignee_display_name": "alice",
            "created": "2026-11-10T09:00:00Z",
            "labels": []
        },
        {
            "id": "10001",
            "key": "OPS-101",
            "project_key": "OPS",
            "summary": "Rotate IAM access keys",
            "status": "In Progress",
            "priority": "High",
            "assignee_display_name": "bob",
            "created": "2026-11-11T09:00:00Z",
            "labels": [
                "finops"
            ]
        },
        {
            "id": "10002",
            "key": "OPS-102",
            "project_key": "OPS",
            "summary": "Untagged EC2 instances",
            "status": "To Do",
            "priority": "Low",
            "assignee_display_name": None,
            "created": "2026-11-12T09:00:00Z",
            "labels": []
        },
        {
            "id": "10003",
            "key": "OPS-103",
            "project_key": "OPS",
            "summary": "Deprecated runtime on Lambda",
            "status": "Done",
            "priority": "Medium",
            "assignee_display_name": "carol",
            "created": "2026-11-13T09:00:00Z",
            "labels": [
                "finops"
            ]
        }
    ],
    "gitlab_project_deployment": [
        {
            "id": "501",
            "project_id": "42",
            "status": "success",
            "environment_name": "production",
            "ref": "main",
            "sha": "0000000000000000000000000000000000000001",
            "created_at": "2026-11-21T12:00:00Z",
            "updated_at": "2026-11-21T12:05:00Z"
        },
        {
            "id": "502",
            "project_id": "42",
            "status": "failed",
            "environment_name": "production",
            "ref": "main",
            "sha": "0000000000000000000000000000000000000002",
            "created_at": "2026-11-22T12:00:00Z",
            "updated_at": "2026-11-22T12:05:00Z"
        },
        {
            "id": "503",
            "project_id": "42",
            "status": "success",
            "environment_name": "staging",
            "ref": "main",
            "sha": "0000000000000000000000000000000000000003",
            "created_at": "2026-11-23T12:00:00Z",
            "updated_at": "2026-11-23T12:05:00Z"
        }
    ],
    "opsgenie_alert": [
        {
            "alert_id": "alert-1",
            "message": "High CPU on i-0000000000000001",
            "status": "open",
            "priority": "P2",
            "source": "CloudWatch",
            "acknowledged": 0,
            "created_at": "2026-11-21T03:11:00Z",
        },
        {
            "alert_id": "alert-2",
            "message": "5xx rate above 2%",
            "status": "open",
            "priority": "P1",
            "source": "CloudWatch",
            "acknowledged": 0,
            "created_at": "2026-11-22T03:12:00Z",
        },
        {
            "alert_id": "alert-3",
            "message": "Disk 90% full",
            "status": "closed",
            "priority": "P3",
            "source": "CloudWatch",
            "acknowledged": 0,
            "created_at": "2026-11-23T03:13:00Z",
        }
    ],
    "microsoft365_team": [
        {
            "id": "team-1",
            "display_name": "Platform",
            "description": "Platform engineering",
            "visibility": "private"
        },
        {
            "id": "team-2",
            "display_name": "Payments",
            "description": "Payments squad",
            "visibility": "private"
        }
    ],
}

from .data_extra import extend as _extend

_extend(TABLES)
