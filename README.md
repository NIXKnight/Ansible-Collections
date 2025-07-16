# Nixknight Ansible Collections

Custom Ansible collections for infrastructure automation and system management.

## Collections

- **nixknight.docker** - Docker container deployment and management
- **nixknight.general** - General Linux system configuration
- **nixknight.opentofu** - OpenTofu/Terraform infrastructure management

## Quick Start

### Installation

Install individual collections from GitHub:

```bash
# Docker collection
ansible-galaxy collection install git+https://github.com/NIXKnight/Ansible-Collections.git#/collections/nixknight/docker,docker-0.1.4

# General collection
ansible-galaxy collection install git+https://github.com/NIXKnight/Ansible-Collections.git#/collections/nixknight/general,general-0.1.0

# OpenTofu collection
ansible-galaxy collection install git+https://github.com/NIXKnight/Ansible-Collections.git#/collections/nixknight/opentofu,opentofu-0.1.2
```

## **License**

This collection is licensed under MIT License (See the LICENSE file).

## **Author**

[Saad Ali](https://github.com/nixknight)
