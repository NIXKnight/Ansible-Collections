from ansible.module_utils.basic import AnsibleModule
import subprocess

def run_command(command):
    """Run a shell command and return output, capturing both stdout and stderr"""
    try:
        # Start the process and capture stdout and stderr
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            text=True
        )
        # Communicate with the process to get results
        stdout, stderr = process.communicate()
        # Return dictionary containing exit code, stdout, and stderr
        return {
            'return_code': process.returncode,
            'stdout': stdout.strip(),
            'stderr': stderr.strip()
        }
    except Exception as e:
        # Return error details if the command fails
        return {
            'return_code': 1,
            'stdout': '',
            'stderr': str(e)
        }

def get_running_docker_containers(project_directory, project_name):
    """Retrieve a list of running containers for a specific Docker Compose project"""
    # Command to change to the specified project directory
    cmd_cd = f"cd {project_directory}"

    # Command to list running container IDs for the project
    cmd_ps = f"docker compose -p {project_name} ps -q --status running"

    # Combine the two commands with && to execute in sequence
    command = f"{cmd_cd} && {cmd_ps}"
    result = run_command(command)

    # Check if the command was successful
    if result['return_code'] != 0:
        # Return an empty list and the error message if there was an error
        return [], result['stderr']

    # Split stdout into individual container IDs if there are any
    container_ids = result['stdout'].split('\n') if result['stdout'] else []
    containers = []

    # Loop through each container ID to retrieve its name
    for container_id in container_ids:
        if not container_id:
            continue

        # Command to inspect the container and get its name
        inspect_cmd = f"docker inspect --format='{{{{.Name}}}}' {container_id}"
        inspect_result = run_command(inspect_cmd)

        # If the command succeeded, strip the leading '/' and store the container details
        if inspect_result['return_code'] == 0:
            container_name = inspect_result['stdout'].strip('/')
            containers.append({
                'id': container_id,
                'name': container_name
            })

    # Return the list of containers and None (no error)
    return containers, None

def main():
    # Define arguments that the module will accept
    module = AnsibleModule(
        argument_spec=dict(
            project_directory=dict(type='str', required=True),
            project_name=dict(type='str', required=True)
        )
    )

    # Get arguments from Ansible
    project_directory = module.params['project_directory']
    project_name = module.params['project_name']

    # Retrieve running containers and any error encountered
    containers, error = get_running_docker_containers(project_directory, project_name)

    # If there is an error, fail the module with an error message
    if error:
        module.fail_json(msg=f"Error checking containers: {error}")

    # Set result with container details and count, without any changes made
    result = {
        'changed': False,
        'containers': containers,
        'container_count': len(containers)
    }

    # Exit module successfully, returning result data
    module.exit_json(**result)

if __name__ == '__main__':
    main()
