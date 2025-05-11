# nixknight.opentofu Collection - Lookup Plugins

This directory contains lookup plugins for the nixknight.opentofu Ansible collection, designed to simplify interactions with OpenTofu (a Terraform fork) state and outputs.

## Installation

Make sure the collection is installed:

```bash
ansible-galaxy collection install git+https://github.com/NIXKnight/Ansible-Collections.git#/collections/nixknight/opentofu,<git tag>
```

## Available Lookup Plugins

### opentofu_output

A lookup plugin for retrieving output values from OpenTofu state files (encrypted and non-encrypted). For encrypted files, it currently only supports PBKDF2 passphrase encryption key provider. It supports multiple backends:
- Local state files
- PostgreSQL database backend
- AWS S3 bucket backend

#### Requirements

This plugin requires the following Python packages:
- psycopg2 (for PostgreSQL backend)
- boto3 (for S3 backend)
- cryptography (for decryption)

#### Usage

```yaml
- name: Get output value from OpenTofu state file
  debug:
    msg: "{{ lookup('nixknight.opentofu.opentofu_output', 'my_output_name', state_file_path='/path/to/terraform.tfstate') }}"
```

#### Examples

**Reading from a local state file:**

```yaml
- name: Get VPC ID from local state file
  debug:
    msg: "VPC ID is {{ lookup('nixknight.opentofu.opentofu_output', 'vpc_id', state_file_path='/path/to/terraform.tfstate') }}"
```

**Reading from PostgreSQL backend:**

```yaml
- name: Get output from PostgreSQL backend
  debug:
    msg: "{{ lookup('nixknight.opentofu.opentofu_output', 'database_url',
             pg_conn_string='postgres://user:password@localhost/terraform_state',
             pg_schema='my_project_state') }}"
```

**Reading from S3 backend:**

```yaml
- name: Get output from S3 backend
  debug:
    msg: "{{ lookup('nixknight.opentofu.opentofu_output', 'instance_ip',
             s3_bucket='my-terraform-state',
             bucket_path='env/prod/terraform.tfstate',
             aws_region='us-west-2',
             aws_profile='production') }}"
```

**Reading from encrypted state:**

```yaml
- name: Get output from encrypted state file
  debug:
    msg: "{{ lookup('nixknight.opentofu.opentofu_output', 'secret_token',
             state_file_path='/path/to/encrypted.tfstate',
             enc_passphrase='my-secure-passphrase',
             enc_key_provider_name='default') }}"
```

#### Parameters

| Parameter | Description | Default | Required |
|-----------|-------------|---------|----------|
| `output_name` | Name of the output to retrieve (first parameter) | n/a | Yes |
| `state_file_path` | Path to local state file | n/a | One of the state sources is required |
| `pg_conn_string` | PostgreSQL connection string | n/a | One of the state sources is required |
| `pg_schema` | PostgreSQL schema name | `terraform_remote_state` | No |
| `s3_bucket` | AWS S3 bucket name | n/a | Required with `bucket_path` |
| `bucket_path` | Path to state file in S3 bucket | n/a | Required with `s3_bucket` |
| `aws_region` | AWS region | `us-east-1` | No |
| `aws_profile` | AWS profile name | n/a | No |
| `enc_passphrase` | Passphrase for decrypting encrypted state | n/a | Required for encrypted state |
| `enc_key_provider_name` | Name of the encryption key provider | n/a | Required with `enc_passphrase` |

## License

MIT

## Author

[Saad Ali](https://github.com/nixknight)
