#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) NIXKnight
# MIT License (see LICENSE)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: docker_compose_service_check
short_description: Report running containers for a Docker Compose project
version_added: "0.1.5"
description:
  - Query a Docker Compose project for its currently running containers.
  - Uses C(docker compose ps --status running --format json) so only running
    containers are returned (in line with the historical C(ps -q) behavior).
  - Read-only -- safe in C(check_mode).
options:
  project_directory:
    description:
      - Absolute path to the directory containing the project's
        C(docker-compose.yml) (or equivalent compose file).
      - Must exist, must be an absolute path, must not contain C(..) segments.
    required: true
    type: path
  project_name:
    description:
      - Compose project name (passed as C(-p)).
      - Must match C(^[a-z0-9][a-z0-9_-]*$) (Compose project-name grammar).
    required: true
    type: str
author:
  - Saad Ali (@NIXKnight)
'''

EXAMPLES = r'''
- name: Inspect running containers of a compose project
  nixknight.docker.docker_compose_service_check:
    project_directory: /opt/postgresql
    project_name: postgresql
  register: pg_check

- name: Show running container count
  ansible.builtin.debug:
    msg: "{{ pg_check.container_count }} container(s) running"
'''

RETURN = r'''
changed:
  description: Always C(false). This module is read-only.
  type: bool
  returned: always
containers:
  description: List of running containers for the given project.
  type: list
  elements: dict
  returned: always
  contains:
    id:
      description: Container ID (short or full, as reported by Compose).
      type: str
    name:
      description: Container name with any leading C(/) stripped.
      type: str
container_count:
  description: Number of running containers reported.
  type: int
  returned: always
'''

import json
import os
import pathlib
import re

from ansible.module_utils.basic import AnsibleModule


PROJECT_NAME_RE = re.compile(r'^[a-z0-9][a-z0-9_-]*$')
CONTAINER_ID_RE = re.compile(r'^[a-f0-9]{12,64}$')


def _validate_project_directory(module, project_directory):
    """Return a validated absolute project directory or fail the module."""
    if not project_directory:
        module.fail_json(msg="project_directory must not be empty")

    if not os.path.isabs(project_directory):
        module.fail_json(
            msg="project_directory must be an absolute path: %s" % project_directory
        )

    resolved = pathlib.Path(project_directory).resolve()
    if ".." in resolved.parts:
        module.fail_json(
            msg="project_directory must not contain '..' segments: %s" % project_directory
        )

    if not os.path.isdir(project_directory):
        module.fail_json(
            msg="project_directory does not exist or is not a directory: %s"
            % project_directory
        )

    return project_directory


def _validate_project_name(module, project_name):
    """Validate the Compose project name against the canonical grammar."""
    if not project_name:
        module.fail_json(msg="project_name must not be empty")

    if not PROJECT_NAME_RE.match(project_name):
        module.fail_json(
            msg=(
                "project_name does not match ^[a-z0-9][a-z0-9_-]*$ "
                "(Compose project-name grammar): %s"
            )
            % project_name
        )

    return project_name


def _parse_compose_ps_json(stdout):
    """Parse `docker compose ps --format json` output.

    Compose versions differ: some emit a single JSON array, others emit
    newline-delimited JSON objects. Handle both.
    """
    stdout = (stdout or "").strip()
    if not stdout:
        return []

    # Try a single JSON document first (array or object).
    try:
        doc = json.loads(stdout)
        if isinstance(doc, list):
            return doc
        if isinstance(doc, dict):
            return [doc]
    except ValueError:
        pass

    # Fall back to NDJSON (one object per line).
    containers = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            containers.append(json.loads(line))
        except ValueError as exc:
            raise ValueError("failed to parse compose ps JSON line: %s" % exc)
    return containers


def get_running_docker_containers(module, project_directory, project_name):
    """Return (containers, error_message) for the named compose project."""
    argv = [
        "docker", "compose",
        "-p", project_name,
        "ps",
        "--status", "running",
        "--format", "json",
    ]

    rc, stdout, stderr = module.run_command(
        argv,
        cwd=project_directory,
        check_rc=False,
    )

    if rc != 0:
        return [], (stderr or "").strip() or "docker compose ps exited with rc=%d" % rc

    try:
        parsed = _parse_compose_ps_json(stdout)
    except ValueError as exc:
        return [], str(exc)

    containers = []
    for entry in parsed:
        # Compose `ps --format json` reports `ID` (full ID), `Name`, `Service`.
        # Use whichever ID-bearing key is present.
        cid = entry.get("ID") or entry.get("Id") or entry.get("ContainerID") or ""
        name = entry.get("Name") or entry.get("Names") or ""

        # Defensive ID validation -- even if the ID came from `docker compose ps`
        # we revalidate to keep the contract narrow.
        if cid and not CONTAINER_ID_RE.match(cid):
            return [], "compose returned a malformed container ID: %s" % cid

        containers.append({
            "id": cid,
            "name": (name or "").lstrip("/"),
        })

    return containers, None


def main():
    module = AnsibleModule(
        argument_spec=dict(
            project_directory=dict(type='path', required=True),
            project_name=dict(type='str', required=True),
        ),
        supports_check_mode=True,
    )

    project_directory = _validate_project_directory(
        module, module.params['project_directory']
    )
    project_name = _validate_project_name(
        module, module.params['project_name']
    )

    containers, error = get_running_docker_containers(
        module, project_directory, project_name
    )

    if error:
        module.fail_json(msg="Error checking containers: %s" % error)

    module.exit_json(
        changed=False,
        containers=containers,
        container_count=len(containers),
    )


if __name__ == '__main__':
    main()
