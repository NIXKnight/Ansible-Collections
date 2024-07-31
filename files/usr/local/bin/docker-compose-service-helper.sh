#!/usr/bin/env bash

# Function to display usage instructions
function usage() {
  echo "Usage: $0 --check-running-containers <project_name> | --stop-running-containers <project_name>"
  exit 1
}

# Function to check running containers for a specific project
function check_running_containers() {
  local PROJECT_NAME="$1"

  # Validate input
  if [ -z "$PROJECT_NAME" ]; then
    echo "Error: Project name is required for checking running containers."
    usage
  fi

  # Get running containers
  local RUNNING_CONTAINERS=$(docker compose -p "$PROJECT_NAME" ps -q --status running)
  local CONTAINERS_LIST_JSON=$(jq -n '[]')

  # Process each running container
  if [ -n "$RUNNING_CONTAINERS" ]; then
    for ID in $RUNNING_CONTAINERS; do
      local CONTAINER_NAME=$(docker inspect --format='{{.Name}}' "$ID" | sed 's/\///')
      CONTAINERS_LIST_JSON=$(echo "$CONTAINERS_LIST_JSON" | jq --arg id "$ID" --arg name "$CONTAINER_NAME" '. + [{id: $id, name: $name}]')
    done
  fi

  # Generate final JSON output
  local FINAL_JSON=$(jq -n --argjson containers_list "$CONTAINERS_LIST_JSON" '{"running_containers": $containers_list}')
  echo -e "${FINAL_JSON}"
}

# Function to stop running containers for a specific project
function stop_running_containers() {
  local PROJECT_NAME="$1"

  # Validate input
  if [ -z "$PROJECT_NAME" ]; then
    echo "Error: Project name is required to stop running containers."
    usage
  fi

  # Stop the containers
  docker compose -p "$PROJECT_NAME" down
}

# Parse options
OPTIONS=$(getopt -o '' --long check-running-containers:,stop-running-containers: -- "$@")
if [ $? -ne 0 ]; then
  usage
fi

eval set -- "$OPTIONS"

# Handle the options
while true; do
  case "$1" in
    --check-running-containers)
      check_running_containers "$2"
      shift 2
      ;;
    --stop-running-containers)
      stop_running_containers "$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    *)
      echo "Invalid option: $1"
      usage
      ;;
  esac
done
