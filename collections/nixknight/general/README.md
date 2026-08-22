# **nixknight.general**

An Ansible collection for general Linux system management. It carries the base-system role used to bring a fresh Debian/Ubuntu host into shape and a generic role for running Python applications out of a virtualenv under systemd, both written against `ansible.builtin` only.

## **Table of Contents**

- [Requirements](#requirements)
- [Contents](#contents)
- [Installation](#installation)
- [License](#license)
- [Author](#author)

## **Requirements**

- Debian-family targets (Debian, Ubuntu)
- Ansible 2.15 or higher
- No external Ansible collection dependencies

## **Contents**

### **Roles**

- **`linux-common`** — comprehensive Linux system configuration and hardening: hostname management, official and third-party APT repositories, package installation, basic `sudo` configuration for a single user, kernel parameters and system optimisation. See [`roles/linux-common/README.md`](roles/linux-common/README.md).
- **`python-venv-app`** — installs and runs any Python application from a git checkout (or pip-only) inside its own virtualenv under a dedicated system user: ordered pip steps under a shared constraints file, rendered configuration and a `0600` environment file for secrets, and a systemd unit restarted only when something changed. See [`roles/python-venv-app/README.md`](roles/python-venv-app/README.md).

## **Installation**

```bash
ansible-galaxy collection install git+https://github.com/NIXKnight/Ansible-Collections.git#/collections/nixknight/general
```

## **License**

This collection is licensed under MIT License (See the LICENSE file).

## **Author**

[Saad Ali](https://github.com/nixknight)
