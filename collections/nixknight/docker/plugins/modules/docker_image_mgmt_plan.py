#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) NIXKnight
# MIT License (see LICENSE)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: docker_image_mgmt_plan
short_description: Compute a Docker image pull/remove plan for a service
version_added: "0.1.5"
description:
  - Inspect the local Docker daemon and produce two lists describing the
    intended image lifecycle for a service: images that need to be pulled
    and images that may be safely removed.
  - Multi-tenant safe -- images referenced by any container on the daemon
    (including stopped containers) are protected from removal.
  - Supports C(check_mode); the inventory read still runs so the planner
    reports an accurate intended plan during dry-runs.
options:
  images:
    description:
      - Service-keyed mapping of desired images. Each value must contain
        C(name) and C(tag).
    required: true
    type: dict
  purge:
    description:
      - When true, all existing tags of the desired image names are added to
        the remove plan (subject to the multi-tenant protection above).
      - Typically set to true during teardown.
    required: false
    type: bool
    default: false
  force_refresh:
    description:
      - When true, every desired image is added to the pull plan even if its
        tag is already present locally. Used for mutable tags (e.g. C(latest))
        to force a re-pull and propagate the resulting C(changed) status to
        the role's restart handler.
    required: false
    type: bool
    default: false
  docker_host:
    description:
      - Optional base URL for the Docker daemon (for example
        C(unix:///var/run/docker.sock) or C(tcp://docker-host:2376)).
      - When omitted, the daemon is discovered from the environment.
    required: false
    type: str
  tls:
    description:
      - Optional TLS configuration mapping passed straight to
        C(docker.tls.TLSConfig).
      - Common keys: C(ca_cert), C(client_cert), C(client_key), C(verify),
        C(assert_hostname).
    required: false
    type: dict
author:
  - Saad Ali (@NIXKnight)
'''

EXAMPLES = r'''
- name: Plan image lifecycle for a service
  nixknight.docker.docker_image_mgmt_plan:
    images:
      postgresql:
        name: "postgres"
        tag: "16.2-bookworm"
      redis:
        name: "redis"
        tag: "7.2.4-bookworm"
  register: plan

- name: Force-refresh mutable tags
  nixknight.docker.docker_image_mgmt_plan:
    images:
      app:
        name: "registry.example.com:5000/foo/app"
        tag: "latest"
    force_refresh: true
  register: refresh_plan
'''

RETURN = r'''
changed:
  description: Always C(false). This module is a planner; it does not pull or remove.
  type: bool
  returned: always
docker_images_to_pull:
  description: List of "name:tag" references that should be pulled.
  type: list
  elements: str
  returned: always
docker_images_to_remove:
  description: List of "name:tag" references that may be removed.
  type: list
  elements: str
  returned: always
'''

import re

from ansible.module_utils.basic import AnsibleModule

try:
    import docker
    from docker.errors import APIError, DockerException, ImageNotFound
    HAS_DOCKER = True
    DOCKER_IMPORT_ERROR = None
except ImportError as imp_exc:
    HAS_DOCKER = False
    DOCKER_IMPORT_ERROR = imp_exc

try:
    from urllib3.exceptions import HTTPError
except ImportError:
    HTTPError = Exception  # type: ignore[misc]


# Reject empty, NUL byte, ASCII control chars, and any whitespace inside the
# reference. The Docker SDK itself enforces the remainder of the
# distribution-spec grammar (incl. valid registry-host-with-port references
# like `registry.example.com:5000/foo`).
_BAD_IMAGE_CHARS = re.compile(r'[\x00-\x1f\s]')


def _sanitize_image_name(module, image_name):
    """Minimal sanitation: defer full validation to the Docker SDK."""
    if not isinstance(image_name, str) or not image_name:
        module.fail_json(msg="image name must be a non-empty string: %r" % (image_name,))
    if _BAD_IMAGE_CHARS.search(image_name):
        module.fail_json(
            msg="image name contains control or whitespace characters: %r"
            % (image_name,)
        )
    return image_name


def _sanitize_image_tag(module, image_tag):
    """Minimal sanitation for the tag component."""
    if not isinstance(image_tag, str) or not image_tag:
        module.fail_json(msg="image tag must be a non-empty string: %r" % (image_tag,))
    if _BAD_IMAGE_CHARS.search(image_tag):
        module.fail_json(
            msg="image tag contains control or whitespace characters: %r" % (image_tag,)
        )
    return image_tag


def _build_docker_client(module, docker_host, tls_params):
    """Construct a DockerClient honoring optional docker_host / tls settings."""
    if not HAS_DOCKER:
        module.fail_json(
            msg=(
                "The 'docker' Python package is required by docker_image_mgmt_plan. "
                "Install it (e.g. via the 'python3-docker' distro package) on the "
                "target host. ImportError: %s"
            )
            % DOCKER_IMPORT_ERROR
        )

    try:
        if docker_host:
            tls_config = None
            if tls_params:
                tls_config = docker.tls.TLSConfig(**tls_params)
            client = docker.DockerClient(base_url=docker_host, tls=tls_config)
        else:
            client = docker.from_env()
        client.ping()
    except (DockerException, HTTPError) as exc:
        module.fail_json(msg="Failed to connect to Docker daemon: %s" % exc)

    return client


def _protected_image_references(client):
    """Return the set of image references currently in use by any container.

    Multi-tenant safety: filters against C(client.containers.list(all=True))
    so containers in created/running/paused/exited states are all considered.
    The protection set is derived from each container's image ID plus its
    current tags -- this catches both tag-referenced and digest-referenced
    deployments on the same daemon.
    """
    protected_tags = set()
    protected_ids = set()
    for container in client.containers.list(all=True):
        image = getattr(container, "image", None)
        if image is None:
            continue
        if getattr(image, "id", None):
            protected_ids.add(image.id)
        for tag in getattr(image, "tags", []) or []:
            protected_tags.add(tag)
    return protected_tags, protected_ids


def _existing_tags_for_image(client, image_name):
    """List all locally present tags for the given image name."""
    try:
        images = client.images.list(name=image_name)
    except APIError as exc:
        raise RuntimeError("Docker API error while listing %s: %s" % (image_name, exc))

    tags = []
    for image in images:
        for tag in image.tags or []:
            tags.append(tag)
    return tags


def get_docker_image_management_plan(module, client, images_config, purge, force_refresh):
    """Compute the pull / remove plan honoring multi-tenant protections."""
    images_to_pull = []
    images_to_remove = []

    protected_tags, protected_ids = _protected_image_references(client)

    for service, config in images_config.items():
        if not isinstance(config, dict):
            module.fail_json(
                msg="images[%s] must be a mapping with 'name' and 'tag' keys" % service
            )

        image_name = _sanitize_image_name(module, config.get('name', ''))
        image_tag = _sanitize_image_tag(module, config.get('tag', ''))
        required_image = "%s:%s" % (image_name, image_tag)

        try:
            existing_images = _existing_tags_for_image(client, image_name)

            if force_refresh:
                # R9: always schedule a pull so the resulting `changed`
                # propagates to the restart handler.
                images_to_pull.append(required_image)

            if required_image not in existing_images:
                if not force_refresh:
                    images_to_pull.append(required_image)
                # Removal candidates: all other tags of this image name that
                # are not protected by an active container reference.
                images_to_remove.extend([
                    img for img in existing_images if img != required_image
                ])
            elif purge:
                # During purge, every tag of this image name is a removal
                # candidate (still subject to the protection filter below).
                images_to_remove.extend(existing_images)
            else:
                # Required tag present: candidates are sibling tags only.
                images_to_remove.extend([
                    img for img in existing_images if img != required_image
                ])

        except ImageNotFound:
            images_to_pull.append(required_image)
        except RuntimeError as exc:
            module.fail_json(msg=str(exc))
        except Exception as exc:  # pylint: disable=broad-except
            module.fail_json(msg="Error checking image %s: %s" % (image_name, exc))

    # Multi-tenant safety filter (S2): drop any candidate that is in use by
    # any container on this daemon (any project, any state).
    filtered_remove = []
    for tag in images_to_remove:
        if tag in protected_tags:
            continue
        # Resolve to the image object so we can check its ID; if the tag is
        # gone before we get here we simply skip it.
        try:
            img = client.images.get(tag)
        except (ImageNotFound, APIError):
            continue
        if getattr(img, "id", None) in protected_ids:
            continue
        filtered_remove.append(tag)

    images_to_pull = list(dict.fromkeys(images_to_pull))
    images_to_remove = list(dict.fromkeys(filtered_remove))

    return images_to_pull, images_to_remove


def main():
    module_args = dict(
        images=dict(type='dict', required=True),
        purge=dict(type='bool', default=False),
        force_refresh=dict(type='bool', default=False),
        docker_host=dict(type='str', required=False, default=None),
        tls=dict(type='dict', required=False, default=None, no_log=False),
    )

    result = dict(
        changed=False,
        docker_images_to_pull=[],
        docker_images_to_remove=[],
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    # S4: the read-only inventory must still run in --check mode so the planner
    # reports accurate drift; the pull/remove tasks (in the role) are the
    # only things that should be skipped.
    client = _build_docker_client(
        module,
        module.params['docker_host'],
        module.params['tls'],
    )

    try:
        images_to_pull, images_to_remove = get_docker_image_management_plan(
            module,
            client,
            module.params['images'],
            module.params['purge'],
            module.params['force_refresh'],
        )
    except Exception as exc:  # pylint: disable=broad-except
        module.fail_json(msg=str(exc))

    result['docker_images_to_pull'] = images_to_pull
    result['docker_images_to_remove'] = images_to_remove

    module.exit_json(**result)


if __name__ == '__main__':
    main()
