# **python-venv-app**

An Ansible role for installing and running **any** Python application inside its own virtualenv, under its own system user, with a systemd unit. The role carries no application-specific logic: it clones a repository (or skips the checkout entirely for a pip-only app), builds a venv with the interpreter you name, runs an **ordered** pip install sequence under a shared constraints file, renders configuration templates and an environment file for secrets, and writes a systemd unit that it restarts only when something actually changed.

## **Table of Contents**

- [Requirements](#requirements)
- [Role Variables](#role-variables)
- [Operational Notes](#operational-notes)
- [Removal](#removal)
- [Installation](#installation)
- [Examples](#examples)
- [License](#license)
- [Author](#author)

## **Requirements**

- Debian-family target (`ansible.builtin.apt` is used for host packages)
- Target host runs systemd
- Ansible 2.15 or higher
- `become: true` at play level: the role escalates to `PVA_USER` for every checkout and pip task
- ACL support on the target (Debian's `acl` package) or `pipelining = True` in `ansible.cfg`, so root can drop to the unprivileged `PVA_USER`; add `acl` to `PVA_APT_PACKAGES` when the host is minimal
- The role is addressed through the play's `collections:` keyword plus its short name (`python-venv-app`), not by FQCN: `ansible-core` validates a fully qualified reference against `^\w+(\.\w+){2,}$`, and `\w` excludes the hyphens in the role name

## **Role Variables**

### **Required Variables**

| Variable | Description | Type |
|----------|-------------|------|
| `PVA_NAME` | Application name; seeds the user, group, unit name and layout. Must match `^[a-z0-9][a-z0-9_.-]*$` | string |

### **Identity and User**

| Variable | Default | Description | Type |
|----------|---------|-------------|------|
| `PVA_USER` | `{{ PVA_NAME }}` | System user the application runs as and that owns the tree | string |
| `PVA_GROUP` | `{{ PVA_USER }}` | Primary group of `PVA_USER` | string |
| `PVA_USER_GROUPS` | `[]` | Supplementary groups, appended (existing membership is never revoked) | list |
| `PVA_USER_SHELL` | `/usr/sbin/nologin` | Login shell of the application user | string |
| `PVA_MANAGE_USER` | `true` | Create the system group and user; `false` when they are provisioned elsewhere | bool |

### **Layout**

| Variable | Default | Description | Type |
|----------|---------|-------------|------|
| `PVA_BASE_DIR` | `/opt/{{ PVA_NAME }}` | Root of everything the role owns (also the user's `home`) | string |
| `PVA_SRC_DIR` | `{{ PVA_BASE_DIR }}/app` | Checkout / application tree; default `WorkingDirectory` and the anchor for relative `dest` paths | string |
| `PVA_VENV_DIR` | `{{ PVA_BASE_DIR }}/venv` | Virtualenv root; created by the first pip task that runs | string |
| `PVA_DIRECTORIES` | `[]` | Extra directories, items `{path, owner, group, mode}`; a relative `path` resolves against `PVA_BASE_DIR`, `owner`/`group` default to `PVA_USER`/`PVA_GROUP`, `mode` to `0755` | list |

### **Host Packages**

| Variable | Default | Description | Type |
|----------|---------|-------------|------|
| `PVA_APT_PACKAGES` | `["git", "python3-venv"]` | Packages installed `state: present` (`update_cache: true`, `cache_valid_time: 3600`). Extend with the application's build/runtime dependencies | list |

### **Source**

| Variable | Default | Description | Type |
|----------|---------|-------------|------|
| `PVA_GIT_REPO` | `""` | Application repository. Empty means a pip-only application: no checkout runs, `PVA_SRC_DIR` is still created | string |
| `PVA_GIT_VERSION` | `HEAD` | Branch, tag or commit to check out | string |
| `PVA_GIT_DEPTH` | `""` | Empty gives a full clone; a value makes the clone shallow (a pinned SHA then needs a depth that reaches it) | int/string |
| `PVA_GIT_FORCE` | `false` | Discard local modifications in the checkout on update | bool |
| `PVA_EXTRA_REPOS` | `[]` | Additional checkouts, items `{repo, dest, version, depth}`; a relative `dest` resolves against `PVA_SRC_DIR`. Their requirements are **not** installed automatically | list |

### **Python and Pip**

| Variable | Default | Description | Type |
|----------|---------|-------------|------|
| `PVA_PYTHON` | `python3` | Interpreter used to build the venv (`<PVA_PYTHON> -m venv`) | string |
| `PVA_VENV_SYSTEM_SITE_PACKAGES` | `false` | Expose the system site-packages inside the venv | bool |
| `PVA_PIP_UPGRADE_PIP` | `true` | Upgrade `pip`, `setuptools` and `wheel` in the venv; being the first pip task it also creates the venv | bool |
| `PVA_PIP_CONSTRAINTS` | `{}` | Map of package to full version specifier (operator included). Rendered to `{{ PVA_BASE_DIR }}/constraints.txt` and passed as `-c` to every pip invocation; not rendered, and removed, when the map is empty | dict |
| `PVA_PIP_STEPS` | `[]` | **Ordered** install sequence, items `{name, packages, requirements, index_url, extra_index_url, extra_args}` | list |

Each `PVA_PIP_STEPS` entry runs its `packages` first, then each file in `requirements` (relative paths resolve against `PVA_SRC_DIR`). `index_url` and `extra_index_url` become `--index-url` / `--extra-index-url` for that step only, and `extra_args` is appended verbatim; the constraints `-c` argument is prepended to all of them.

### **Configuration**

| Variable | Default | Description | Type |
|----------|---------|-------------|------|
| `PVA_TEMPLATES` | `[]` | Templates rendered into the tree, items `{src, dest, owner, group, mode, no_log}`; a relative `dest` resolves against `PVA_SRC_DIR`, `owner`/`group` default to `PVA_USER`/`PVA_GROUP`, `mode` to `0644` | list |
| `PVA_FILES` | `[]` | Static files copied into the tree; identical item schema | list |
| `PVA_ENVIRONMENT` | `{}` | `KEY: value` map rendered to `PVA_ENV_FILE` as `KEY=value` lines, `0600`, owned by `PVA_USER`, always `no_log` with the diff suppressed | dict |
| `PVA_ENV_FILE` | `{{ PVA_BASE_DIR }}/{{ PVA_NAME }}.env` | Environment file path; wired into the unit as `EnvironmentFile=` only while the map is non-empty, and removed when it is empty | string |

### **Service**

| Variable | Default | Description | Type |
|----------|---------|-------------|------|
| `PVA_MANAGE_SERVICE` | `true` | Write and manage a systemd unit. `false` for libraries, CLI tools and one-shot apps: the venv is built and no unit is written | bool |
| `PVA_SERVICE_NAME` | `{{ PVA_NAME }}` | Unit name | string |
| `PVA_SERVICE_FILE` | `/etc/systemd/system/{{ PVA_SERVICE_NAME }}.service` | Unit file path | string |
| `PVA_SERVICE_DESCRIPTION` | `{{ PVA_NAME }}` | `Description=` | string |
| `PVA_SERVICE_AFTER` | `network-online.target` | `After=` (omitted when empty) | string |
| `PVA_SERVICE_WANTS` | `network-online.target` | `Wants=` (omitted when empty) | string |
| `PVA_SERVICE_REQUIRES` | `""` | `Requires=` (omitted when empty) | string |
| `PVA_SERVICE_COMMAND` | `{{ PVA_VENV_DIR }}/bin/python -u main.py` | `ExecStart=` command, before arguments | string |
| `PVA_SERVICE_ARGS` | `[]` | Arguments joined with spaces and appended to the command | list |
| `PVA_SERVICE_WORKING_DIR` | `{{ PVA_SRC_DIR }}` | `WorkingDirectory=` | string |
| `PVA_SERVICE_TYPE` | `simple` | `Type=` | string |
| `PVA_SERVICE_RESTART` | `on-failure` | `Restart=` | string |
| `PVA_SERVICE_RESTART_SEC` | `5` | `RestartSec=` | int |
| `PVA_SERVICE_TIMEOUT_STOP_SEC` | `60` | `TimeoutStopSec=` | int |
| `PVA_SERVICE_NO_NEW_PRIVILEGES` | `true` | `NoNewPrivileges=` | bool |
| `PVA_SERVICE_PRIVATE_TMP` | `true` | `PrivateTmp=` | bool |
| `PVA_SERVICE_EXTRA_UNIT_OPTIONS` | `[]` | Raw `Key=Value` lines appended to `[Unit]` | list |
| `PVA_SERVICE_EXTRA_SERVICE_OPTIONS` | `[]` | Raw `Key=Value` lines appended to `[Service]` (`MemoryMax=`, `Nice=`, `SupplementaryGroups=`, `Environment=`, ...) | list |
| `PVA_SERVICE_ENABLED` | `true` | Enable the unit at boot | bool |
| `PVA_SERVICE_STATE` | `started` | Target state when nothing changed: `started` or `stopped` | string |

### **Removal**

| Variable | Default | Description | Type |
|----------|---------|-------------|------|
| `PVA_REMOVE` | `false` | When `true`, run the teardown path instead of create/update | bool |

## **Operational Notes**

- **Restart on change, computed inline**: the unit is restarted when *any* of the following reported `changed` in this run -- the application checkout, an extra repository, the pip toolchain upgrade, the constraints file, any pip step, any template, any copied file, the environment file, or the unit file itself. The restart happens only while `PVA_SERVICE_STATE` is `started`; with `stopped` the role stops the unit and changes nothing else.
- **No handlers, on purpose**: this role is meant to be applied several times in one play with different parameters (several applications on one host). A handler would fire once at play end, with the last application's variables, and restart the wrong unit. The state decision is therefore a `set_fact` immediately followed by a single `ansible.builtin.systemd_service` task, per application.
- **Ordered pip, one constraints file**: `PVA_PIP_STEPS` is a sequence, not a set. Step order is the contract: install the index-hosted wheels you care about first (a CUDA torch build, for example), then the application's `requirements.txt`, so pip's resolver cannot quietly swap the pinned build for a PyPI one. `PVA_PIP_CONSTRAINTS` is the belt to that braces -- it applies to every step, including the `pip`/`setuptools`/`wheel` upgrade.
- **Extra repositories are not scanned**: `PVA_EXTRA_REPOS` clones plugins and custom nodes, nothing more. If a plugin ships a `requirements.txt`, name it in a `PVA_PIP_STEPS` entry. Explicit beats magic when a plugin's requirements can pull a different torch.
- **The venv is created by pip**: `ansible.builtin.pip` builds it via `virtualenv_command` on first use. With `PVA_PIP_UPGRADE_PIP: false` **and** an empty `PVA_PIP_STEPS`, no venv is ever created.
- **Ownership**: checkouts and pip run as `PVA_USER` (`become_user`), so the tree, the venv and everything generated at runtime are owned by the service account without a chown sweep afterwards. This needs `become: true` at play level and ACL support (or pipelining) on the target.
- **Relative paths**: `dest` in `PVA_TEMPLATES` / `PVA_FILES` / `PVA_EXTRA_REPOS` and each entry of a step's `requirements` resolve against `PVA_SRC_DIR`; `path` in `PVA_DIRECTORIES` resolves against `PVA_BASE_DIR`. Absolute paths are used as given.
- **Secrets**: put them in `PVA_ENVIRONMENT` (vaulted) and read them from the process environment, or set `no_log: true` on the secret-bearing template item. Both paths suppress the module diff as well as the task output.

### **Switching Versions**

Bump `PVA_GIT_VERSION` (and the pins in `PVA_PIP_CONSTRAINTS`, and any version in `PVA_PIP_STEPS`), then re-run the role. The checkout moves, the affected pip steps report `changed`, and the restart-on-change rule takes the service through the new code in the same run. Downgrades work the same way, provided the pins are exact -- a shallow `PVA_GIT_DEPTH` is the one trap, since the older commit may not be in the clone.

### **Removal**

`PVA_REMOVE: true` stops and disables the unit, deletes the unit file and reloads systemd (all three only while `PVA_MANAGE_SERVICE` is true, and the stop is skipped when the unit file is already gone), deletes `PVA_ENV_FILE`, deletes `PVA_BASE_DIR` (checkout, venv and constraints file with it), and deletes the user and group when `PVA_MANAGE_USER` is true. Entries of `PVA_DIRECTORIES` that live **outside** `PVA_BASE_DIR` are deliberately left in place: that is where models, datasets and outputs are usually parked.

## **Installation**

Install the collection containing this role:

```bash
ansible-galaxy collection install git+https://github.com/NIXKnight/Ansible-Collections.git#/collections/nixknight/general
```

## **Examples**

### **ComfyUI with a Pinned CUDA Torch and a Custom Node**

```yaml
- name: Setup ComfyUI
  hosts: all
  become: true
  vars:
    PVA_NAME: "comfyui"
    PVA_USER_GROUPS:
      - "video"
      - "render"
    PVA_APT_PACKAGES:
      - "git"
      - "python3-venv"
      - "acl"
      - "ffmpeg"
      - "libgl1"
    PVA_GIT_REPO: "https://github.com/Comfy-Org/ComfyUI.git"
    PVA_GIT_VERSION: "v0.33.1"
    PVA_EXTRA_REPOS:
      - repo: "https://github.com/city96/ComfyUI-GGUF.git"
        version: "6ea2651e7df66d7585f6ffee804b20e92fb38b8a"
        dest: "custom_nodes/ComfyUI-GGUF"
    PVA_DIRECTORIES:
      - path: "/var/lib/comfyui/models"
      - path: "/var/lib/comfyui/output"
    PVA_PIP_CONSTRAINTS:
      torch: "==2.11.0+cu130"
      torchvision: "==0.26.0+cu130"
      torchaudio: "==2.11.0+cu130"
    PVA_PIP_STEPS:
      - name: "torch"
        packages:
          - "torch"
          - "torchvision"
          - "torchaudio"
        index_url: "https://download.pytorch.org/whl/cu130"
      - name: "comfyui"
        packages:
          - "gguf==0.19.0"
        requirements:
          - "requirements.txt"
          - "custom_nodes/ComfyUI-GGUF/requirements.txt"
    PVA_TEMPLATES:
      - src: "templates/comfyui/extra_model_paths.yaml.j2"
        dest: "extra_model_paths.yaml"
    PVA_SERVICE_DESCRIPTION: "ComfyUI"
    PVA_SERVICE_AFTER: "network-online.target docker.service"
    PVA_SERVICE_COMMAND: "{{ PVA_VENV_DIR }}/bin/python -u main.py"
    PVA_SERVICE_ARGS:
      - "--listen"
      - "127.0.0.1,172.17.0.1"
      - "--port"
      - "8188"
      - "--cuda-device"
      - "0"
  collections:
    - nixknight.general
  roles:
    - role: python-venv-app
```

The torch trio installs from the CUDA index first; ComfyUI's own `requirements.txt` and the custom node's requirements install afterwards under `-c constraints.txt`, so neither can replace the `+cu130` wheels.

### **A pip-only FastAPI Service**

```yaml
- name: Setup Metrics API
  hosts: all
  become: true
  vars:
    PVA_NAME: "metrics-api"
    PVA_PIP_STEPS:
      - name: "runtime"
        packages:
          - "fastapi"
          - "uvicorn[standard]"
    PVA_FILES:
      - src: "files/metrics-api/app.py"
        dest: "app.py"
    PVA_ENVIRONMENT:
      API_KEY: "<vaulted>"
      LOG_LEVEL: "info"
    PVA_SERVICE_DESCRIPTION: "Metrics API"
    PVA_SERVICE_COMMAND: "{{ PVA_VENV_DIR }}/bin/uvicorn app:app"
    PVA_SERVICE_ARGS:
      - "--host"
      - "127.0.0.1"
      - "--port"
      - "8000"
  collections:
    - nixknight.general
  roles:
    - role: python-venv-app
```

No `PVA_GIT_REPO`, so nothing is cloned: `app.py` is copied into `PVA_SRC_DIR` and the venv is built from the single pip step. `API_KEY` belongs in a vaulted variable; it is written to `/opt/metrics-api/metrics-api.env` (`0600`) and reaches the process through `EnvironmentFile=`.

## **License**

This role is licensed under MIT License (See the LICENSE file).

## **Author**

[Saad Ali](https://github.com/nixknight)
