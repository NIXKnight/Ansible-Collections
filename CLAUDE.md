# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Structure

This is an Ansible Collections repository containing custom modules, roles, and lookup plugins organized under the `nixknight` namespace. The repository contains three main collections:

### Collections Architecture

- **nixknight.docker**: Docker container deployment and management
  - Automated Docker Compose service lifecycle management
  - Container and image management with cleanup capabilities

- **nixknight.general**: General Linux system configuration
  - Comprehensive Linux system setup
  - Package management and system configuration automation

- **nixknight.opentofu**: OpenTofu/Terraform infrastructure management
  - OpenTofu state output lookup plugin that also reads passphrase-encrypted OpenTofu state with PostgreSQL and S3 backend support
  - Automated infrastructure deployment and configuration

## Key Components

### Docker Collection Components

**Custom Modules:**
- **`docker_compose_service_check.py`**: Checks Docker Compose service status and running containers with detailed state reporting
- **`docker_image_mgmt_plan.py`**: Manages Docker image lifecycle (pull/remove/purge) with comprehensive cleanup capabilities including container removal and orphaned image cleanup

**Roles:**
- **`docker-compose-service`**: Manages Docker Compose services with systemd integration, supporting both creation and deletion of services, template-based configuration, and service health monitoring

### General Collection Components

**Roles:**
- **`linux-common`**: Comprehensive Linux system configuration and hardening including hostname management, package installation, sudo configuration, security policies, and system optimization

### OpenTofu Collection Components

**Lookup Plugins:**
- **`opentofu_output.py`**: Advanced lookup plugin for extracting OpenTofu outputs from encrypted state files with support for multiple backends (S3, PostgreSQL), PBKDF2 key derivation, AES-GCM encryption, and comprehensive error handling

**Roles:**
- **`opentofu`**: Automated OpenTofu module deployment with backend configuration, state encryption, variable management, and deployment validation

## Development Guidelines

### Working with Collections
- Each collection has its own `galaxy.yml` with version and metadata
- Modules are located in `collections/nixknight/{collection}/plugins/modules/`
- Roles are located in `collections/nixknight/{collection}/roles/`
- All collections use MIT license

### Testing and Validation
- Use `ansible-playbook --check` for dry-run validation
- Test modules with `ansible -m` for individual module testing
- Role testing should include variable validation and idempotency checks
- Collection versioning workflows ensure quality and compatibility
- Comprehensive README files provide testing examples and usage patterns

### Code Patterns
- All custom modules follow standard Ansible module structure with `AnsibleModule`
- Error handling uses appropriate `module.fail_json()` calls
- Docker operations use both subprocess and docker-py library approaches
- OpenTofu integration uses `community.general.terraform` module

## File Organization
```
collections/nixknight/
├── docker/           # Docker-related automation
│   ├── roles/        # Docker Compose service management
│   └── plugins/      # Custom Docker modules
├── general/          # General Linux system management
│   └── roles/        # Linux system configuration
└── opentofu/         # Infrastructure as Code with OpenTofu
    ├── roles/        # OpenTofu deployment automation
    └── plugins/      # OpenTofu lookup plugins
```

Each collection is self-contained with its own `galaxy.yml` and extensive template systems for flexible deployment scenarios.

## GitHub Actions Workflows

The repository includes automated CI/CD workflows for collection management:

### Collection Auto-Versioning
**File:** `.github/workflows/collection-auto-versioning.yml`
- **Trigger:** Pull requests that modify collection files (`collections/nixknight/*/**`)
- **Purpose:** Automatically increments patch version in `galaxy.yml` for modified collections
- **Features:**
  - Identifies which collection was changed in the PR
  - Calculates next patch version based on existing git tags
  - Updates `galaxy.yml` with new version if needed
  - Commits version changes directly to the PR branch
  - Prevents PRs that modify multiple collections simultaneously

### Collection Tagging
**File:** `.github/workflows/collection-tagging.yml`
- **Trigger:** Pushes to main branch that modify collection files (`collections/nixknight/*/**`)
- **Purpose:** Creates git tags for released collection versions
- **Features:**
  - Reads version from `galaxy.yml` of the modified collection
  - Creates annotated git tags in format `{collection-name}-{version}`
  - Only creates tags if they don't already exist
  - Ensures single collection changes per push to main branch

Both workflows work together to provide automated semantic versioning and release management for individual collections within the repository.
