from ansible.module_utils.basic import AnsibleModule
import docker
from docker.errors import APIError, ImageNotFound
from urllib3.exceptions import HTTPError

def get_existing_docker_images(client, image_name):
    """
    Get all tags for a specific image name using Docker API.
    Returns a list of "name:tag" strings.

    Args:
        client: Docker client instance
        image_name: Name of the image to check
    """
    try:
        # List all images matching the specified image name
        images = client.images.list(name=image_name)
        image_tags = []
        for image in images:
            # Each image may have multiple tags, add each tag to image_tags list
            for tag in image.tags:
                image_tags.append(tag)
        return image_tags
    except APIError as e:
        # Handle Docker API errors and raise a descriptive exception
        raise Exception(f"Docker API error while getting images: {str(e)}")

def get_docker_image_management_plan(module, docker_images_config):
    """
    Determine which images need to be pulled and which should be removed.
    Uses Docker API to check image existence.

    Args:
        module: Ansible module instance
        docker_images_config: Dictionary of service image configurations
    """
    try:
        # Initialize Docker client using environment configuration
        client = docker.from_env()
        # Test Docker daemon connectivity
        client.ping()
    except (docker.errors.DockerException, HTTPError) as e:
        # Fail if unable to connect to Docker daemon
        module.fail_json(msg=f"Failed to connect to Docker daemon: {str(e)}")

    # Lists to store images that need to be pulled or removed
    docker_images_to_pull = []
    docker_images_to_remove = []

    # Loop through each service and image configuration
    for service, config in docker_images_config.items():
        image_name = config['name']
        image_tag = config['tag']
        required_image = f"{image_name}:{image_tag}"

        try:
            # Get all tags for the specified image name
            existing_images = get_existing_docker_images(client, image_name)

            # Check if the specified tag exists among existing images
            if required_image not in existing_images:
                # If not found, mark for pulling and remove any other tags
                docker_images_to_pull.append(required_image)
                docker_images_to_remove.extend(existing_images)
            else:
                # Required tag exists; remove any other tags for this image
                docker_images_to_remove.extend([
                    img for img in existing_images
                    if img != required_image
                ])

        except ImageNotFound:
            # If image not found, add it to the pull list
            docker_images_to_pull.append(required_image)
        except Exception as e:
            # Handle general errors during image check
            module.fail_json(msg=f"Error checking image {image_name}: {str(e)}")

    # Remove duplicates from lists while maintaining order
    docker_images_to_pull = list(dict.fromkeys(docker_images_to_pull))
    docker_images_to_remove = list(dict.fromkeys(docker_images_to_remove))

    return docker_images_to_pull, docker_images_to_remove

def main():
    # Define input arguments for the Ansible module
    module_args = dict(
        images=dict(type='dict', required=True)
    )

    # Initialize result dictionary to store results and status
    result = dict(
        changed=False,
        docker_images_to_pull=[],
        docker_images_to_remove=[],
        failed=False
    )

    # Initialize Ansible module
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    try:
        # If not in check mode, perform the image analysis
        if not module.check_mode:
            docker_images_to_pull, docker_images_to_remove = get_docker_image_management_plan(
                module,
                module.params['images']
            )

            # Update result dictionary with the analysis outcomes
            result['docker_images_to_pull'] = docker_images_to_pull
            result['docker_images_to_remove'] = docker_images_to_remove

        # Exit module with the result as JSON
        module.exit_json(**result)

    except Exception as e:
        # Handle any errors that occur during execution
        module.fail_json(msg=str(e))

if __name__ == '__main__':
    main()
