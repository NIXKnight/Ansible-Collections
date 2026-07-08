# **nixknight.kubernetes**

An Ansible collection for Kubernetes-adjacent bare-metal automation. Its first role builds **Talos Linux boot media for bare-metal installs** — per-node-class ISO and PXE assets, with an optional guarded USB-write path — using only `ansible.builtin` (no cloud dependencies).

## **Table of Contents**

- [Requirements](#requirements)
- [Contents](#contents)
- [Installation](#installation)
- [License](#license)
- [Author](#author)

## **Requirements**

- Ansible 2.15 or higher (per `meta/runtime.yml`)
- For the Talos Factory backend: outbound HTTPS to the Talos Image Factory
- For the Talos imager backend: a working Docker CLI on the build host
- No external Ansible collection dependencies

## **Contents**

### **Roles**

- **`talos-baremetal-image`** — renders a Talos Image Factory schematic per node class (or runs the `siderolabs/imager` container offline), produces local metal ISO + PXE assets, records a build manifest (schematic id, asset paths, recorded sha256s, and the matching `metal-installer` image ref), and can optionally write a chosen ISO to a USB device behind hard safety guards. See [`roles/talos-baremetal-image/README.md`](roles/talos-baremetal-image/README.md).

## **Installation**

```bash
ansible-galaxy collection install git+https://github.com/NIXKnight/Ansible-Collections.git#/collections/nixknight/kubernetes
```

## **License**

This collection is licensed under MIT License (See the LICENSE file).

## **Author**

[Saad Ali](https://github.com/nixknight)
