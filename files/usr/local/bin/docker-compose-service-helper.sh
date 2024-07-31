#!/usr/bin/env bash

# Function to display usage instructions
function usage() {
  echo -e "Usage: $0 [OPTIONS] <ARGUMENT>"
  echo -e ""
  echo -e "OPTIONS:"
  echo -e "  --check-running-containers <project_name>  Check all running Docker containers for the specified project."
  echo -e "                                             Outputs a JSON list of running containers with their IDs and names."
  echo -e ""
  echo -e "  --stop-running-containers <project_name>   Stop all running Docker containers for the specified project."
  echo -e "                                             This will bring down all containers managed by the Docker Compose project."
  echo -e ""
  echo -e "  --create-image-mgmt-plan <input_json>      Create a plan to manage Docker images based on the provided input JSON."
  echo -e "                                             The input JSON should specify the image names and tags for each service."
  echo -e "                                             Outputs a JSON list of images to pull and images to remove."
  echo -e ""
  echo -e "ARGUMENTS:"
  echo -e "  <project_name>   The name of the Docker Compose project. This is required for the --check-running-containers and"
  echo -e "                   --stop-running-containers options."
  echo -e ""
  echo -e "  <input_json>     The JSON input describing the Docker images to manage. This is required for the --create-image-mgmt-plan option."
  echo -e ""
  echo -e "EXAMPLES:"
  echo -e "  $0 --check-running-containers my_project"
  echo -e "  $0 --stop-running-containers my_project"
  echo -e "  $0 --create-image-mgmt-plan '{\"web\": {\"name\": \"nginx\", \"tag\": \"latest\"}, \"db\": {\"name\": \"postgres\", \"tag\": \"13\"}}'"
  echo -e ""
  echo -e "Note: This script is intended for managing Docker containers and images within a Docker Compose environment."
  echo -e "      Ensure that Docker Compose is installed and that the project name matches the one defined in your Docker Compose file."
  echo -e ""
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

# Function to get the image ID for a specific image name
function get_image_id() {
  docker images --format "{{.ID}}" "$1"
}

# Function to create a management plan for Docker images based on input JSON
function create_image_mgmt_plan() {
  local INPUT_IMAGES_JSON=$1
  local IMAGES_TO_PULL=()
  local IMAGES_TO_REMOVE=()

  # Parse the input JSON and iterate over each service
  for SERVICE in $(echo "$INPUT_IMAGES_JSON" | jq -r 'keys[]'); do
    # Extract image name and tag for the service
    local IMAGE_NAME=$(echo "$INPUT_IMAGES_JSON" | jq -r --arg SERVICE "$SERVICE" '.[$SERVICE].name')
    local IMAGE_TAG=$(echo "$INPUT_IMAGES_JSON" | jq -r --arg SERVICE "$SERVICE" '.[$SERVICE].tag')
    local FULL_IMAGE="$IMAGE_NAME:$IMAGE_TAG"

    # Get the existing image ID if it exists
    local EXISTING_IMAGE_ID=$(get_image_id "$IMAGE_NAME")

    # If the image does not exist locally, add it to the pull list
    if [ -z "$EXISTING_IMAGE_ID" ]; then
      IMAGES_TO_PULL+=("$FULL_IMAGE")
    else
      # Check if the existing image version matches the desired tag
      local EXISTING_IMAGE_VERSION=$(docker inspect --format='{{.RepoTags}}' $EXISTING_IMAGE_ID | sed 's/\[\|\]//g' | awk -F ':' '{print $2}')
      # If the versions do not match, add the old image to the remove list and the new one to the pull list
      if [ "$EXISTING_IMAGE_VERSION" != "$IMAGE_TAG" ]; then
        IMAGES_TO_REMOVE+=("$IMAGE_NAME:$EXISTING_IMAGE_VERSION")
        IMAGES_TO_PULL+=("$FULL_IMAGE")
      fi
    fi
  done

  # Generate the final JSON output with lists of images to pull and remove
  local FINAL_JSON=$(jq -n \
    --argjson images_to_pull "$(printf '%s\n' "${IMAGES_TO_PULL[@]}" | jq -R . | jq -s .)" \
    --argjson images_to_remove "$(printf '%s\n' "${IMAGES_TO_REMOVE[@]}" | jq -R . | jq -s .)" \
    '{images_to_pull: $images_to_pull, images_to_remove: $images_to_remove}')

  echo -e "${FINAL_JSON}"
  exit 0
}

# Parse options
OPTIONS=$(getopt -o '' --long check-running-containers:,stop-running-containers:,create-image-mgmt-plan: -- "$@")
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
    --create-image-mgmt-plan)
      create_image_mgmt_plan "$2"
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
