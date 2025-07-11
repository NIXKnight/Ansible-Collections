# **docker-compose-service**

An Ansible role for deploying and managing Docker Compose services with systemd integration. This role automates the deployment of containerized services, creates systemd service files for service management, and handles Docker image lifecycle management.

## **Table of Contents**

- [Requirements](#requirements)
- [Role Variables](#role-variables)
- [Dependencies](#dependencies)
- [Installation](#installation)
- [Features](#features)
- [Examples](#examples)
- [License](#license)
- [Author](#author)

## **Requirements**

- Docker installed and running on target hosts
- systemd service manager
- Ansible 2.9 or higher
- Python docker library on target hosts (for image management)

## **Role Variables**

### **Required Variables**

| Variable | Description | Type |
|----------|-------------|------|
| `DOCKER_COMPOSE_SERVICE_NAME` | Name of the service for systemd | string |
| `DOCKER_COMPOSE_SERVICE_COMPOSE_PATH` | Path where docker-compose.yml will be stored | string |
| `DOCKER_COMPOSE_SERVICE_MANIFEST` | Docker Compose configuration content | dict |

### **Optional Variables**

| Variable | Default | Description | Type |
|----------|---------|-------------|------|
| `DOCKER_COMPOSE_SERVICE_SYSTEMD_DESCRIPTION` | `"{{ DOCKER_COMPOSE_SERVICE_NAME }} Service"` | Systemd service description | string |
| `DOCKER_COMPOSE_SERVICE_SYSTEMD_REQUIRES` | `docker.service` | Systemd service dependencies | string |
| `DOCKER_COMPOSE_SERVICE_SYSTEMD_AFTER` | `docker.service` | Systemd service ordering | string |
| `DOCKER_COMPOSE_SERVICE_SYSTEMD_FILE` | `/etc/systemd/system/{{ DOCKER_COMPOSE_SERVICE_NAME }}.service` | Systemd service file path | string |
| `DOCKER_COMPOSE_SERVICE_CONFIG_PATH` | `""` | Additional configuration directory path | string |
| `DOCKER_COMPOSE_SERVICE_IMAGES` | `{}` | Docker images to manage with tags | dict |
| `DOCKER_COMPOSE_SERVICE_FILES` | `[]` | Static files to copy to target | list |
| `DOCKER_COMPOSE_SERVICE_TEMPLATES` | `[]` | Template files to render | list |
| `DOCKER_COMPOSE_SERVICE_ADDITIONAL_PATHS` | `[]` | Additional directories to create | list |

## **Installation**

Install the collection containing this role:

```bash
ansible-galaxy collection install git+https://github.com/NIXKnight/Ansible-Collections.git#/collections/nixknight/docker,docker-0.1.3
```

## **Examples**

### **PostgreSQL Service**
Here is an example of how to use this role to set up a PostgreSQL service.

```yaml
- name: Setup PostgreSQL Service
  hosts: all
  become: true
  vars:
    DOCKER_COMPOSE_SERVICE_NAME: "postgresql"
    DOCKER_COMPOSE_SERVICE_COMPOSE_PATH: "/opt/postgresql"
    DOCKER_COMPOSE_SERVICE_IMAGES:
      postgresql:
        name: "postgres"
        tag: "16.2-bookworm"
    DOCKER_COMPOSE_SERVICE_MANIFEST:
      dest: "{{ DOCKER_COMPOSE_SERVICE_COMPOSE_PATH }}/docker-compose.yml"
      content:
        services:
          postgres:
            image: "{{ DOCKER_COMPOSE_SERVICE_IMAGES.postgresql.name }}:{{ DOCKER_COMPOSE_SERVICE_IMAGES.postgresql.tag }}"
            container_name: postgresql
            restart: unless-stopped
            environment:
              POSTGRES_USER: user
              POSTGRES_PASSWORD: password
              POSTGRES_DB: my_database
            volumes:
              - "postgres_data:/var/lib/postgresql/data"
            ports:
              - "5432:5432"
            healthcheck:
              test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
              interval: 10s
              timeout: 5s
              retries: 5
              start_period: 30s
        volumes:
          postgres_data:
            driver: local
  roles:
    - role: nixknight.docker.docker-compose-service
```

### **Django Service with Custom Configuration**
Here is an example of how to use this role to set up a Django service with a custom configuration file and a PostgreSQL backend.

```yaml
- name: Setup Django Service with PostgreSQL
  hosts: all
  become: true
  vars:
    DOCKER_COMPOSE_SERVICE_NAME: "django-app"
    DOCKER_COMPOSE_SERVICE_COMPOSE_PATH: "/opt/django-app"
    DOCKER_COMPOSE_SERVICE_CONFIG_PATH: "/opt/django-app/config"
    DOCKER_COMPOSE_SERVICE_IMAGES:
      django:
        name: "python"
        tag: "3.9-slim"
      postgresql:
        name: "postgres"
        tag: "16.2-bookworm"
    DOCKER_COMPOSE_SERVICE_FILES:
      - src: "files/django/production.py"
        dest: "{{ DOCKER_COMPOSE_SERVICE_CONFIG_PATH }}/production.py"
        mode: "0644"
        owner: "root"
        group: "root"
    DOCKER_COMPOSE_SERVICE_MANIFEST:
      dest: "{{ DOCKER_COMPOSE_SERVICE_COMPOSE_PATH }}/docker-compose.yml"
      content:
        services:
          django:
            image: "{{ DOCKER_COMPOSE_SERVICE_IMAGES.django.name }}:{{ DOCKER_COMPOSE_SERVICE_IMAGES.django.tag }}"
            container_name: django_app
            restart: unless-stopped
            volumes:
              - "./app:/app"
              - "{{ DOCKER_COMPOSE_SERVICE_CONFIG_PATH }}/production.py:/app/project/settings/production.py"
            ports:
              - "8000:8000"
            depends_on:
              postgres:
                condition: service_healthy
            command: "python manage.py runserver 0.0.0.0:8000"
          postgres:
            image: "{{ DOCKER_COMPOSE_SERVICE_IMAGES.postgresql.name }}:{{ DOCKER_COMPOSE_SERVICE_IMAGES.postgresql.tag }}"
            container_name: postgres_for_django
            restart: unless-stopped
            environment:
              POSTGRES_USER: django_user
              POSTGRES_PASSWORD: django_password
              POSTGRES_DB: django_db
            volumes:
              - "postgres_data:/var/lib/postgresql/data"
            healthcheck:
              test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
              interval: 10s
              timeout: 5s
              retries: 5
              start_period: 30s
        volumes:
          postgres_data:
            driver: local
  roles:
    - role: nixknight.docker.docker-compose-service
```

### **PostgreSQL Service (Role Vars Pattern)**

```yaml
- name: Setup PostgreSQL Service (Role Vars Pattern)
  hosts: all
  become: true
  vars:
    POSTGRESQL_SERVICE_NAME: "postgresql-pattern"
    POSTGRESQL_SERVICE_SYSTEMD_DESCRIPTION: "PostgreSQL Service (Pattern)"
    POSTGRESQL_SERVICE_SYSTEMD_REQUIRES: "docker.service"
    POSTGRESQL_SERVICE_SYSTEMD_AFTER: "docker.service"
    POSTGRESQL_SERVICE_SYSTEMD_FILE: "/etc/systemd/system/{{ POSTGRESQL_SERVICE_NAME }}.service"
    POSTGRESQL_SERVICE_COMPOSE_PATH: "/opt/postgresql-pattern"
    POSTGRESQL_SERVICE_CONFIG_PATH: ""
    POSTGRESQL_SERVICE_TEMPLATES: []
    POSTGRESQL_SERVICE_ADDITIONAL_PATHS: []
    POSTGRESQL_SERVICE_IMAGES:
      postgresql:
        name: "postgres"
        tag: "16.2-bookworm"
    POSTGRESQL_SERVICE_MANIFEST:
      dest: "{{ POSTGRESQL_SERVICE_COMPOSE_PATH }}/docker-compose.yml"
      content:
        services:
          postgres:
            image: "{{ POSTGRESQL_SERVICE_IMAGES.postgresql.name }}:{{ POSTGRESQL_SERVICE_IMAGES.postgresql.tag }}"
            container_name: postgresql-pattern
            restart: unless-stopped
            environment:
              POSTGRES_USER: user
              POSTGRES_PASSWORD: password
              POSTGRES_DB: my_database_pattern
            volumes:
              - "postgres_pattern_data:/var/lib/postgresql/data"
            ports:
              - "5433:5432"
            healthcheck:
              test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
              interval: 10s
              timeout: 5s
              retries: 5
              start_period: 30s
        volumes:
          postgres_pattern_data:
            driver: local
  roles:
    - role: nixknight.docker.docker-compose-service
      DOCKER_COMPOSE_SERVICE_NAME: "{{ POSTGRESQL_SERVICE_NAME }}"
      DOCKER_COMPOSE_SERVICE_SYSTEMD_DESCRIPTION: "{{ POSTGRESQL_SERVICE_SYSTEMD_DESCRIPTION }}"
      DOCKER_COMPOSE_SERVICE_SYSTEMD_REQUIRES: "{{ POSTGRESQL_SERVICE_SYSTEMD_REQUIRES }}"
      DOCKER_COMPOSE_SERVICE_SYSTEMD_AFTER: "{{ POSTGRESQL_SERVICE_SYSTEMD_AFTER }}"
      DOCKER_COMPOSE_SERVICE_SYSTEMD_FILE: "{{ POSTGRESQL_SERVICE_SYSTEMD_FILE }}"
      DOCKER_COMPOSE_SERVICE_IMAGES: "{{ POSTGRESQL_SERVICE_IMAGES }}"
      DOCKER_COMPOSE_SERVICE_COMPOSE_PATH: "{{ POSTGRESQL_SERVICE_COMPOSE_PATH }}"
      DOCKER_COMPOSE_SERVICE_MANIFEST: "{{ POSTGRESQL_SERVICE_MANIFEST }}"
      DOCKER_COMPOSE_SERVICE_CONFIG_PATH: "{{ POSTGRESQL_SERVICE_CONFIG_PATH }}"
      DOCKER_COMPOSE_SERVICE_TEMPLATES: "{{ POSTGRESQL_SERVICE_TEMPLATES }}"
      DOCKER_COMPOSE_SERVICE_ADDITIONAL_PATHS: "{{ POSTGRESQL_SERVICE_ADDITIONAL_PATHS }}"
```

### **Django Service with Custom Configuration (Role Vars Pattern)**

```yaml
- name: Setup Django Service with PostgreSQL (Role Vars Pattern)
  hosts: all
  become: true
  vars:
    DJANGO_APP_SERVICE_NAME: "django-app-pattern"
    DJANGO_APP_SERVICE_SYSTEMD_DESCRIPTION: "Django App Service (Pattern)"
    DJANGO_APP_SERVICE_SYSTEMD_REQUIRES: "docker.service"
    DJANGO_APP_SERVICE_SYSTEMD_AFTER: "docker.service"
    DJANGO_APP_SERVICE_SYSTEMD_FILE: "/etc/systemd/system/{{ DJANGO_APP_SERVICE_NAME }}.service"
    DJANGO_APP_SERVICE_COMPOSE_PATH: "/opt/django-app-pattern"
    DJANGO_APP_SERVICE_CONFIG_PATH: "/opt/django-app-pattern/config"
    DJANGO_APP_SERVICE_TEMPLATES: []
    DJANGO_APP_SERVICE_ADDITIONAL_PATHS: []
    DJANGO_APP_SERVICE_IMAGES:
      django:
        name: "python"
        tag: "3.9-slim"
      postgresql:
        name: "postgres"
        tag: "16.2-bookworm"
    DJANGO_APP_SERVICE_FILES:
      - src: "files/django/production.py"
        dest: "{{ DJANGO_APP_SERVICE_CONFIG_PATH }}/production.py"
        mode: "0644"
        owner: "root"
        group: "root"
    DJANGO_APP_SERVICE_MANIFEST:
      dest: "{{ DJANGO_APP_SERVICE_COMPOSE_PATH }}/docker-compose.yml"
      content:
        services:
          django:
            image: "{{ DJANGO_APP_SERVICE_IMAGES.django.name }}:{{ DJANGO_APP_SERVICE_IMAGES.django.tag }}"
            container_name: django_app_pattern
            restart: unless-stopped
            volumes:
              - "./app:/app"
              - "{{ DJANGO_APP_SERVICE_CONFIG_PATH }}/production.py:/app/project/settings/production.py"
            ports:
              - "8001:8000"
            depends_on:
              postgres:
                condition: service_healthy
            command: "python manage.py runserver 0.0.0.0:8000"
          postgres:
            image: "{{ DJANGO_APP_SERVICE_IMAGES.postgresql.name }}:{{ DJANGO_APP_SERVICE_IMAGES.postgresql.tag }}"
            container_name: postgres_for_django_pattern
            restart: unless-stopped
            environment:
              POSTGRES_USER: django_user_pattern
              POSTGRES_PASSWORD: django_password_pattern
              POSTGRES_DB: django_db_pattern
            volumes:
              - "postgres_django_pattern_data:/var/lib/postgresql/data"
            healthcheck:
              test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
              interval: 10s
              timeout: 5s
              retries: 5
              start_period: 30s
        volumes:
          postgres_django_pattern_data:
            driver: local
  roles:
    - role: nixknight.docker.docker-compose-service
      DOCKER_COMPOSE_SERVICE_NAME: "{{ DJANGO_APP_SERVICE_NAME }}"
      DOCKER_COMPOSE_SERVICE_SYSTEMD_DESCRIPTION: "{{ DJANGO_APP_SERVICE_SYSTEMD_DESCRIPTION }}"
      DOCKER_COMPOSE_SERVICE_SYSTEMD_REQUIRES: "{{ DJANGO_APP_SERVICE_SYSTEMD_REQUIRES }}"
      DOCKER_COMPOSE_SERVICE_SYSTEMD_AFTER: "{{ DJANGO_APP_SERVICE_SYSTEMD_AFTER }}"
      DOCKER_COMPOSE_SERVICE_SYSTEMD_FILE: "{{ DJANGO_APP_SERVICE_SYSTEMD_FILE }}"
      DOCKER_COMPOSE_SERVICE_IMAGES: "{{ DJANGO_APP_SERVICE_IMAGES }}"
      DOCKER_COMPOSE_SERVICE_COMPOSE_PATH: "{{ DJANGO_APP_SERVICE_COMPOSE_PATH }}"
      DOCKER_COMPOSE_SERVICE_MANIFEST: "{{ DJANGO_APP_SERVICE_MANIFEST }}"
      DOCKER_COMPOSE_SERVICE_CONFIG_PATH: "{{ DJANGO_APP_SERVICE_CONFIG_PATH }}"
      DOCKER_COMPOSE_SERVICE_TEMPLATES: "{{ DJANGO_APP_SERVICE_TEMPLATES }}"
      DOCKER_COMPOSE_SERVICE_ADDITIONAL_PATHS: "{{ DJANGO_APP_SERVICE_ADDITIONAL_PATHS }}"
      DOCKER_COMPOSE_SERVICE_FILES: "{{ DJANGO_APP_SERVICE_FILES }}"

## **License**

This role is licensed under MIT License (See the LICENSE file).

## **Author**

[Saad Ali](https://github.com/nixknight)
