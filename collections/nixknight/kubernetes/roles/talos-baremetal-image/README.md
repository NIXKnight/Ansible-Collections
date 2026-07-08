# **talos-baremetal-image**

An Ansible role that builds **Talos Linux boot media for bare-metal installs** — one set of assets per node class. For each profile it renders a Talos Image Factory schematic (or runs the `siderolabs/imager` container offline), produces local **metal ISO** and **PXE** assets, records a manifest of everything it built, and can optionally write a chosen ISO to a USB device behind hard safety guards. It has zero cloud dependencies and uses only `ansible.builtin`.

## **Table of Contents**

- [Requirements](#requirements)
- [Role Variables](#role-variables)
- [Profiles](#profiles)
- [Operational Notes](#operational-notes)
- [Installation](#installation)
- [Examples](#examples)
- [License](#license)
- [Author](#author)

## **Requirements**

- Ansible 2.15 or higher (per the collection `meta/runtime.yml`)
- Run on a build host (often `localhost`) that has outbound HTTPS to the Talos Image Factory (factory backend) **or** a working Docker CLI (imager backend)
- `lsblk`, `findmnt`, `readlink`, and `dd` available on the host when using the optional USB-write path (`util-linux` + `coreutils`); `xz` is additionally required for the `raw` USB source format
- No external Ansible collections are required (pure `ansible.builtin`) — a deliberate divergence from cloud-snapshot builders

## **Role Variables**

### **Required Variables**

This role ships working defaults for every variable and has **no strictly required inputs**. In practice you will override at least `TBI_IMAGE_PROFILES` (extension sets per node class) and usually `TBI_TALOS_VERSION` and `TBI_OUTPUT_DIR`.

### **Optional Variables**

| Variable | Default | Description | Type |
|----------|---------|-------------|------|
| `TBI_TALOS_VERSION` | `v1.12.7` | Talos release used for every profile unless overridden per profile | string |
| `TBI_BUILD_BACKEND` | `factory` | `factory` (Image Factory HTTP API) or `imager` (offline container builds) | string |
| `TBI_FACTORY_API` | `https://factory.talos.dev` | Talos Image Factory endpoint (factory backend) | string |
| `TBI_IMAGER_IMAGE` | `ghcr.io/siderolabs/imager` | Imager container image; the role appends `:<version>` (imager backend) | string |
| `TBI_DEFAULT_ARCH` | `amd64` | Architecture for any profile that omits `arch` (`amd64` or `arm64`) | string |
| `TBI_OUTPUT_DIR` | `{{ playbook_dir }}/talos-images` | Root output directory; each profile gets its own subdirectory | string |
| `TBI_IMAGE_PROFILES` | 4 profiles (see [Profiles](#profiles)) | Per-node-class image definitions | list |
| `TBI_VALIDATE_EXTENSIONS` | `true` | Treat a non-200 Factory schematic response as fatal, and require pinned `extension_images` digests on the imager backend | bool |
| `TBI_VERIFY_CHECKSUM` | `true` | Enable expected-hash verification when a profile supplies `expected_checksums` (otherwise sha256 is only recorded) | bool |
| `TBI_API_RETRIES` | `3` | Retries for Factory API calls and downloads | int |
| `TBI_API_DELAY` | `10` | Delay (seconds) between retries | int |
| `TBI_DOWNLOAD_TIMEOUT` | `1200` | Per-download timeout (seconds) for `get_url` | int |
| `TBI_CREATE_MANIFEST` | `true` | Write `manifest.json` under `TBI_OUTPUT_DIR` | bool |
| `TBI_USB_WRITE_ENABLE` | `false` | Master switch for the destructive USB-write path | bool |
| `TBI_USB_DEVICE` | `""` | Target device; a stable `/dev/disk/by-id/...` path is required unless overridden | string |
| `TBI_USB_ALLOW_UNSTABLE_DEVICE` | `false` | Allow a bare `/dev/sdX` target instead of a `/dev/disk/by-id/...` path (not recommended) | bool |
| `TBI_USB_CONFIRM` | `false` | Second confirmation flag; must be `true` together with `TBI_USB_WRITE_ENABLE` | bool |
| `TBI_USB_PROFILE` | `""` | Name of the profile whose asset is written to USB | string |
| `TBI_USB_SOURCE_FORMAT` | `iso` | `iso` (write the isohybrid ISO) or `raw` (decompress `.raw.xz` through `dd`) | string |
| `TBI_DIR_MODE` | `0750` | Mode for directories created by the role | string |
| `TBI_ASSET_MODE` | `0644` | Mode for downloaded / generated boot assets | string |
| `TBI_SCHEMATIC_MODE` | `0600` | Mode for the rendered schematic kept for audit | string |
| `TBI_MANIFEST_MODE` | `0644` | Mode for `manifest.json` | string |

### **Per-Profile Keys**

Each entry in `TBI_IMAGE_PROFILES` supports:

| Key | Required | Description |
|-----|----------|-------------|
| `name` | yes | Profile name (`^[a-z0-9][a-z0-9_-]*$`); also the output subdirectory |
| `arch` | no | `amd64` (default) or `arm64` |
| `formats` | yes | Subset of `[iso, pxe, raw]` |
| `role` | no | Organizational only (`controlplane` / `worker`); does **not** change the image |
| `extensions` | no | Factory official extension names (factory backend) |
| `kernel_args` | no | Extra kernel args (Factory schematic, and the imager iPXE boot line) |
| `meta` | no | List of `{key, value}` Factory meta entries |
| `overlay` | no | `{name, image}` overlay for SBC targets |
| `talos_version` | no | Override `TBI_TALOS_VERSION` for this profile |
| `schematic_id` | no | Use a pre-computed Factory schematic id and skip generation |
| `extension_images` | no | Pinned digest refs (`…@sha256:<64 hex>`), **imager backend only** |
| `expected_checksums` | no | Map of asset basename → sha256 for real verification |
| `secureboot` | no | **RESERVED, unimplemented in v1** — must be `false` |

## **Profiles**

The default `TBI_IMAGE_PROFILES` ships four node classes, all `amd64`, all building `iso` + `pxe`:

| Profile | `role` | Extensions |
|---------|--------|------------|
| `control-plane` | `controlplane` | `iscsi-tools`, `util-linux-tools` |
| `worker` | `worker` | `iscsi-tools`, `util-linux-tools` |
| `worker-gpu` | `worker` | `nonfree-kmod-nvidia-production`, `nvidia-container-toolkit-production` |
| `worker-storage` | `worker` | `iscsi-tools`, `util-linux-tools`, `drbd` |

A Talos *metal* image does **not** itself encode control-plane-vs-worker — that distinction lives in the machine config applied after first boot. Profiles differentiate **images** by extension set / kernel args / meta / overlay / arch; the `role` key is purely organizational (naming and output grouping).

## **Operational Notes**

- **This role does NOT embed machine config into images by default.** Boot media produced here is generic for its node class. Embedding role-specific machine config into an image is possible upstream but would blur the control-plane/worker boundary and is intentionally out of scope. Apply machine config after the node boots.
- **Boot media is not the installer.** The ISO/PXE assets only boot the node; the first-boot install/upgrade pulls the matching installer image. For the factory backend the role records `factory.talos.dev/metal-installer/<schematic_id>:<talos_version>` per profile in the manifest. Reference that image in your machine config / upgrade flow.
- **Checksums are recorded, not verified, by default.** The role records the sha256 of each produced asset into the manifest. That is provenance bookkeeping, **not** an authenticity proof. Real verification runs only when `TBI_VERIFY_CHECKSUM` is `true` **and** a profile supplies `expected_checksums` for the asset basename, in which case a mismatch fails the run. Nothing here is "sha256-verified" by default — it is "sha256 recorded (+ optional expected-hash verification)".
- **Extension validation is Factory's, not a guessed endpoint.** For the factory backend, extensions are validated by POSTing the schematic to `/schematics`; an unknown extension or invalid field makes Factory return a non-200 response, which the role treats as fatal (when `TBI_VALIDATE_EXTENSIONS`). The role never GETs a guessed "official extensions list". For the imager backend, `extension_images` must be **explicit, pinned digest refs** that you resolve out of band, e.g. `crane export ghcr.io/siderolabs/extensions:<ver> | tar x -O image-digests | grep <name>`; the role asserts they are pinned and never guesses them.
- **PXE handling differs by backend.** Factory PXE downloads the Factory-hosted iPXE script from `…/pxe/<id>/<version>/metal-<arch>` (it references Factory-hosted kernel/initramfs); the role does not hardcode kernel/initramfs filenames. Imager PXE runs the imager with `--output-kind kernel` and `--output-kind initramfs` and additionally renders a local iPXE file (`boot.ipxe.j2`) — Talos does **not** embed extra kernel args into the PXE kernel/initramfs, so kernel args are placed on the iPXE boot line. Set `TBI_IPXE_BASE_URL` to point the iPXE file at your HTTP(S) host serving the kernel/initramfs.
- **Extensions are not a complete stack.** The bundled extension choices boot the kernel pieces only. NVIDIA still requires the Talos/Kubernetes NVIDIA runtime class and the device plugin; `drbd` requires the matching userspace/operator; `util-linux-tools` is a minimal/contrib helper set, not generally required. Treat extensions as one layer, not a turnkey solution.
- **SecureBoot is deferred.** The `secureboot` per-profile key is reserved but unimplemented in v1 (it needs distinct `*-secureboot.iso` asset names plus signing/key inputs). Profiles must keep it `false`; the role refuses `true` rather than ship a half-wired path.
- **The USB-write path is destructive and OFF by default.** It runs only when `TBI_USB_WRITE_ENABLE` and `TBI_USB_CONFIRM` are both `true` and `TBI_USB_DEVICE` is a `/dev/...` path. It then: requires a stable `/dev/disk/by-id/...` device (unless `TBI_USB_ALLOW_UNSTABLE_DEVICE`), resolves symlinks to the **whole** disk, rejects partitions, rejects non-removable disks, rejects any `crypt`/`lvm`/`raid`/`dm` holders, rejects mounted children, and rejects the disk backing `/` (compared by `MAJ:MIN`, not by name). It prints the target model/serial/size before writing, runs `dd` as root, and never runs in check mode. Even with all guards, **double-check the device** — `dd` is unforgiving.
- **Idempotency.** `get_url` (factory) and `command` with `creates:` (imager) skip work when the target asset already exists; delete an asset to force a rebuild. The recorded manifest always reflects what is currently on disk.
- **Intended host.** The role produces files on the host it targets; `TBI_OUTPUT_DIR` defaults to a `playbook_dir`-relative path, so running against `localhost` (or a dedicated build host) keeps the manifest paths meaningful.

## **Installation**

Install the collection containing this role:

```bash
ansible-galaxy collection install git+https://github.com/NIXKnight/Ansible-Collections.git#/collections/nixknight/kubernetes
```

The collection has no external collection dependencies.

## **Examples**

### **Build All Default Profiles via the Factory**

```yaml
- name: Build Talos bare-metal boot media
  hosts: localhost
  connection: local
  gather_facts: true
  vars:
    TBI_TALOS_VERSION: "v1.12.7"
    TBI_OUTPUT_DIR: "/srv/talos-images"
  roles:
    - role: nixknight.kubernetes.talos-baremetal-image
```

### **Custom Profiles With Kernel Args, Meta, and a Pinned Schematic**

```yaml
- name: Build custom Talos boot media
  hosts: localhost
  connection: local
  gather_facts: true
  vars:
    TBI_OUTPUT_DIR: "/srv/talos-images"
    TBI_IMAGE_PROFILES:
      - name: "control-plane"
        role: "controlplane"
        arch: "amd64"
        extensions:
          - "siderolabs/iscsi-tools"
          - "siderolabs/util-linux-tools"
        kernel_args:
          - "console=ttyS0,115200n8"
        meta:
          - key: 10
            value: "example-machine-config-marker"
        formats:
          - "iso"
          - "pxe"
      - name: "worker-arm"
        role: "worker"
        arch: "arm64"
        extensions:
          - "siderolabs/iscsi-tools"
        formats:
          - "iso"
  roles:
    - role: nixknight.kubernetes.talos-baremetal-image
```

### **Offline Build via the Imager With Pinned Extension Digests**

```yaml
- name: Build Talos boot media offline with the imager
  hosts: localhost
  connection: local
  gather_facts: true
  vars:
    TBI_BUILD_BACKEND: "imager"
    TBI_OUTPUT_DIR: "/srv/talos-images"
    TBI_IMAGE_PROFILES:
      - name: "worker-storage"
        role: "worker"
        arch: "amd64"
        # Resolve digests out of band, e.g.:
        #   crane export ghcr.io/siderolabs/extensions:v1.12.7 \
        #     | tar x -O image-digests | grep iscsi-tools
        extension_images:
          - "ghcr.io/siderolabs/iscsi-tools@sha256:0000000000000000000000000000000000000000000000000000000000000000"
          - "ghcr.io/siderolabs/drbd@sha256:1111111111111111111111111111111111111111111111111111111111111111"
        kernel_args:
          # talos.platform=metal is already on the generated iPXE boot line;
          # list only genuinely-extra args here.
          - "net.ifnames=0"
        formats:
          - "iso"
          - "pxe"
  roles:
    - role: nixknight.kubernetes.talos-baremetal-image
```

### **Write a Built ISO to a USB Device (Destructive, Explicit Opt-In)**

```yaml
- name: Write a Talos ISO to a USB stick
  hosts: localhost
  connection: local
  gather_facts: true
  become: true
  vars:
    TBI_OUTPUT_DIR: "/srv/talos-images"
    TBI_USB_WRITE_ENABLE: true
    TBI_USB_CONFIRM: true
    TBI_USB_PROFILE: "control-plane"
    TBI_USB_SOURCE_FORMAT: "iso"
    # Always prefer a stable by-id path. Verify it points at the USB stick.
    TBI_USB_DEVICE: "/dev/disk/by-id/usb-SanDisk_Ultra_4C530001234567890123-0:0"
  roles:
    - role: nixknight.kubernetes.talos-baremetal-image
```

### **Verify Recorded Hashes Against Expected Values**

```yaml
- name: Build and verify Talos boot media against known hashes
  hosts: localhost
  connection: local
  gather_facts: true
  vars:
    TBI_OUTPUT_DIR: "/srv/talos-images"
    TBI_VERIFY_CHECKSUM: true
    TBI_IMAGE_PROFILES:
      - name: "control-plane"
        role: "controlplane"
        arch: "amd64"
        extensions:
          - "siderolabs/iscsi-tools"
        formats:
          - "iso"
        expected_checksums:
          metal-amd64.iso: "0000000000000000000000000000000000000000000000000000000000000000"
  roles:
    - role: nixknight.kubernetes.talos-baremetal-image
```

## **License**

This role is licensed under MIT License (See the LICENSE file).

## **Author**

[Saad Ali](https://github.com/nixknight)
