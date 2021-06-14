#!/usr/bin/env python

from pathlib import Path
import argparse
import os
import re

# set's REPO to whatever the repository is named
REPO = Path(__file__).parents[1].absolute().name
REPO_PATH = Path(__file__).parents[1].absolute().as_posix()
# ------------------------------------------------------------------------------

'''
A CLI for developing and deploying an app deeply integrated with this
repository's structure. Written to be python version agnostic.
'''


def get_info():
    '''
    Returns:
        str: System args and environment as a dict.
    '''
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description='A CLI for developing and deploying {repo} containers.'.format(repo=REPO),
        usage='\n\tpython cli.py COMMAND [-a --args]=ARGS [-h --help]'
    )

    parser.add_argument('command',
                        metavar='command',
                        type=str,
                        nargs=1,
                        action='store',
                        help='''Command to run in {repo} app.

    app          - Run Flask app inside {repo} container
    build        - Build image of {repo}
    build-prod   - Build production image of {repo}
    container    - Display the Docker container id for {repo} app
    coverage     - Generate coverage report for {repo} app
    destroy      - Shutdown {repo} app and destroy its Docker image
    destroy-prod - Shutdown {repo}-prod container and destroy its Docker image
    docs         - Generate documentation for {repo} app
    fast-test    - Run testing on {repo} app skipping tests marked as slow
    full-docs    - Generates documentation, coverage report and metrics
    image        - Display the Docker image id for {repo} app
    lab          - Start a Jupyter lab server
    lint         - Run linting and type checking on {repo} app code
    package      - Build {repo} pip package
    prod         - Start {repo} production app
    publish      - Publish repository to python package index.
    push         - Push production of {repo} image to Dockerhub
    python       - Run python interpreter session inside {repo} container
    remove       - Remove {repo} app Docker image
    restart      - Restart {repo} app
    requirements - Write frozen requirements to disk
    start        - Start {repo} app
    state        - State of {repo} app
    stop         - Stop {repo} app
    test         - Run testing on {repo} app
    tox          - Run tox tests on {repo}
    version      - Updates version and runs full-docs and requirements
    zsh          - Run ZSH session inside {repo} container
'''.format(repo=REPO))

    parser.add_argument(
        '-a',
        '--args',
        metavar='args',
        type=str,
        nargs='+',
        action='store',
        help='Additional arguments to be passed. Be sure to include hyphen prefixes.'
    )

    temp = parser.parse_args()
    mode = temp.command[0]
    args = []
    if temp.args is not None:
        args = re.split(' +', temp.args[0])

    compose_path = Path(REPO_PATH, 'docker/docker-compose.yml')
    compose_path = compose_path.as_posix()

    user = '{}:{}'.format(os.geteuid(), os.getegid())

    info = dict(
        args=args,
        mode=mode,
        compose_path=compose_path,
        user=user
    )
    return info


def get_fix_permissions_command(info, directory):
    '''
    Recursively reverts permissions of given directory from user.

    Args:
        directory (str): Directory to be recursively chowned.

    Returns:
        str: Command.
    '''
    cmd = "{exec} chown -R {user} {directory}".format(
        exec=get_docker_exec_command(),
        user=info['user'],
        directory=directory
    )
    return cmd


def get_architecture_diagram_command():
    '''
    Generates a svg file detailing this repository's module structure.

    Returns:
        str: Command.
    '''
    cmd = '{exec} python3.7 -c "'
    cmd += "import re; from rolling_pin.repo_etl import RepoETL; "
    cmd += "etl = RepoETL('/home/ubuntu/{repo}/python'); "
    cmd += "regex = 'test|mock'; "
    cmd += "data = etl._data.copy(); "
    cmd += "func = lambda x: not bool(re.search(regex, x)); "
    cmd += "mask = data.node_name.apply(func); "
    cmd += "data = data[mask]; "
    cmd += "data.reset_index(inplace=True, drop=True); "
    cmd += "data.dependencies = data.dependencies"
    cmd += ".apply(lambda x: list(filter(func, x))); "
    cmd += "etl._data = data; "
    cmd += "etl.write('/home/ubuntu/{repo}/docs/architecture.svg', orient='lr')"
    cmd += '"'
    cmd = cmd.format(repo=REPO, exec=get_docker_exec_command())
    return cmd


def get_radon_metrics_command():
    '''
    Generates radon metrics of this repository as html files.

    Returns:
        str: Command.
    '''
    cmd = '{exec} python3.7 -c "from rolling_pin.radon_etl import RadonETL; '
    cmd += "etl = RadonETL('/home/ubuntu/{repo}/python'); "
    cmd += "etl.write_plots('/home/ubuntu/{repo}/docs/plots.html'); "
    cmd += "etl.write_tables('/home/ubuntu/{repo}/docs'); "
    cmd += '"'
    cmd = cmd.format(repo=REPO, exec=get_docker_exec_command())
    return cmd


def get_remove_pycache_command():
    '''
    Removes all pycache files and directories under the repo's main directory.

    Returns:
        str: Command.
    '''
    cmd = r"find {repo_path} | grep -E '__pycache__|\.pyc$' | "
    cmd += "parallel 'rm -rf {x}'"
    cmd = cmd.format(repo_path=REPO_PATH, x='{}')
    return cmd


# COMMANDS----------------------------------------------------------------------
def get_app_command():
    '''
    Starts Flask app.

    Returns:
        str: Command.
    '''
    exec = get_docker_exec_command(
        env_vars=['DEBUG_MODE=True', 'REPO_ENV=True']
    )
    cmd = "{exec} python3.7 /home/ubuntu/{repo}/python/{repo}/server/app.py"
    cmd = cmd.format(exec=exec, repo=REPO)
    return cmd


def get_container_id_command():
    '''
    Gets current container id.

    Returns:
        str: Command.
    '''
    cmd = "docker ps -a --filter name={repo} --format '{pattern}'"
    cmd = cmd.format(repo=REPO, pattern='{{.ID}}')
    return cmd


def get_coverage_command(info):
    '''
    Runs pytest coverage.

    Args:
        info (dict): Info dictionary.

    Returns:
        str: Command.
    '''
    cmd = '{exec} mkdir -p /home/ubuntu/{repo}/docs && {test} '
    cmd += '--cov=/home/ubuntu/{repo}/python '
    cmd += '--cov-config=/home/ubuntu/{repo}/docker/pytest.ini '
    cmd += '--cov-report=html:/home/ubuntu/{repo}/docs/htmlcov '
    cmd = cmd.format(
        repo=REPO,
        exec=get_docker_exec_command(),
        test=get_test_command(info),
    )
    return cmd


def get_docs_command():
    '''
    Build documentation.

    Returns:
        str: Fully resolved build docs command.
    '''
    cmd = '{exec} mkdir -p /home/ubuntu/{repo}/docs && '
    cmd += '{exec} zsh -c "'
    cmd += 'pandoc /home/ubuntu/{repo}/README.md -o /home/ubuntu/{repo}/sphinx/intro.rst && '
    cmd += 'sphinx-build /home/ubuntu/{repo}/sphinx /home/ubuntu/{repo}/docs && '
    cmd += 'cp /home/ubuntu/{repo}/sphinx/style.css /home/ubuntu/{repo}/docs/_static/style.css && '
    cmd += 'touch /home/ubuntu/{repo}/docs/.nojekyll && '
    cmd += 'mkdir -p /home/ubuntu/{repo}/docs/resources '
    cmd += '"'
    cmd = cmd.format(repo=REPO, exec=get_docker_exec_command())
    return cmd


def get_image_id_command():
    '''
    Gets currently built image id.

    Returns:
        str: Command.
    '''
    cmd = "docker images {repo} --format '{pattern}'"
    cmd = cmd.format(repo=REPO, pattern='{{.ID}}')
    return cmd


def get_lab_command():
    '''
    Start a jupyter lab server.

    Returns:
        str: Command.
    '''
    cmd = '{exec} jupyter lab --allow-root --ip=0.0.0.0 --no-browser'
    cmd = cmd.format(exec=get_docker_exec_command())
    return cmd


def get_lint_command():
    '''
    Runs flake8 linting on python code.

    Returns:
        str: Command.
    '''
    cmd = '{exec} flake8 /home/ubuntu/{repo}/python '
    cmd += '--config /home/ubuntu/{repo}/docker/flake8.ini'
    cmd = cmd.format(repo=REPO, exec=get_docker_exec_command())
    return cmd


def get_type_checking_command():
    '''
    Runs mypy type checking on python code.

    Returns:
        str: Command.
    '''
    cmd = '{exec} mypy /home/ubuntu/{repo}/python '
    cmd += '--config-file /home/ubuntu/{repo}/docker/mypy.ini'
    cmd = cmd.format(repo=REPO, exec=get_docker_exec_command())
    return cmd


def get_build_image_command():
    '''
    Create docker image.

    Returns:
        str: Command.
    '''
    cmd = 'cd docker; '
    cmd += 'docker build --force-rm --no-cache '
    cmd += '--file dev.dockerfile '
    cmd += '--tag {repo}:latest .; '
    cmd += 'cd ..'
    cmd = cmd.format(repo=REPO, repo_path=REPO_PATH)
    return cmd


def get_build_production_image_command():
    '''
    Create production docker image.

    Returns:
        str: Command.
    '''
    cmd = 'cd docker; '
    cmd += 'docker build --force-rm --no-cache '
    cmd += '--file prod.dockerfile '
    cmd += '--tag thenewflesh/{repo}:$VERSION .; '
    cmd += 'cd ..'
    cmd = cmd.format(repo=REPO, repo_path=REPO_PATH)
    return cmd


def get_production_container_command(info):
    '''
    Run production docker container.

    Args:
        info (dict): Info dictionary.

    Returns:
        str: Command.
    '''
    if info['args'] == ['']:
        cmd = 'echo "Please provide a directory to map into the container '
        cmd += 'after the -a flag."'
        return cmd

    cmd = 'docker run '
    cmd += '--volume {volume}:/mnt/storage '
    cmd += '--publish 8080:8080 '
    cmd += '--name {repo}-prod '
    cmd += 'thenewflesh/{repo}:$VERSION && '
    cmd = cmd.format(volume=info['args'][0], repo=REPO)
    return cmd


def get_destroy_production_container_command():
    '''
    Destroy production container and image.

    Returns:
        str: Command.
    '''
    cmd = 'cd docker; '
    cmd += 'docker stop {repo}-prod && '
    cmd += 'docker rm {repo}-prod && '
    cmd += 'docker image remove {repo}-prod; '
    cmd += 'cd ..'
    cmd = cmd.format(repo=REPO, repo_path=REPO_PATH)
    return cmd


def get_publish_command():
    '''
    Publish repository to python package index.

    Returns:
        str: Command.
    '''
    cmd = '{exec} twine upload dist/* && '
    cmd += '{exec2} rm -rf /tmp/{repo} '
    cmd = cmd.format(
        repo=REPO,
        exec=get_docker_exec_command('/tmp/' + REPO, env_vars=[]),
        exec2=get_docker_exec_command(env_vars=[]),
    )
    return cmd


def get_push_to_dockerhub_command(info):
    '''
    Push production image to dockerhub.

    Args:
        info (dict): Info dictionary.

    Returns:
        str: Command.
    '''
    cmd = 'docker push thenewflesh/{repo}:$VERSION'
    cmd = cmd.format(repo=REPO)
    return cmd


def get_package_command():
    '''
    Build pip package.

    Returns:
        str: Command.
    '''
    cmd = '{exec} zsh -c "'
    cmd += 'rm -rf /tmp/{repo} && '
    cmd += 'cp -R /home/ubuntu/{repo}/python /tmp/{repo} && '
    cmd += 'cp /home/ubuntu/{repo}/README.md /tmp/{repo}/README.md && '
    cmd += 'cp /home/ubuntu/{repo}/LICENSE /tmp/{repo}/LICENSE && '
    cmd += 'cp /home/ubuntu/{repo}/pip/MANIFEST.in /tmp/{repo}/MANIFEST.in && '
    cmd += 'cp /home/ubuntu/{repo}/pip/setup.cfg /tmp/{repo}/ && '
    cmd += 'cp /home/ubuntu/{repo}/pip/setup.py /tmp/{repo}/ && '
    cmd += 'cp /home/ubuntu/{repo}/pip/version.txt /tmp/{repo}/ && '
    cmd += 'cp /home/ubuntu/{repo}/docker/dev_requirements.txt /tmp/{repo}/ && '
    cmd += 'cp /home/ubuntu/{repo}/docker/prod_requirements.txt /tmp/{repo}/ && '
    cmd += 'cp -r /home/ubuntu/{repo}/templates /tmp/{repo}/{repo} && '
    cmd += 'cp -r /home/ubuntu/{repo}/resources /tmp/{repo}/{repo} && '
    cmd += "find /tmp/{repo}/{repo}/resources -type f | grep -vE 'icon|test_' "
    cmd += "| parallel 'rm -rf {x}'; "
    cmd += r"find /tmp/{repo} | grep -E '.*test.*\.py$|mock.*\.py$|__pycache__'"
    cmd += " | parallel 'rm -rf {x}'; "
    cmd += "find /tmp/{repo} -type f | grep __init__.py | parallel '"
    cmd += "rm -rf {x}; touch {x}'"
    cmd += '" && '
    cmd += '{exec2} python3.7 setup.py sdist '
    cmd = cmd.format(
        x='{}',
        repo=REPO,
        exec=get_docker_exec_command(env_vars=[]),
        exec2=get_docker_exec_command('/tmp/' + REPO, env_vars=[]),
    )
    return cmd


def get_python_command():
    '''
    Opens a python interpreter inside a running container.

    Returns:
        str: Command.
    '''
    cmd = "{exec} python3.7".format(exec=get_docker_exec_command())
    return cmd


def get_variables_command(info):
    '''
    Gets command for setting variables.

    Args:
        info (dict): Info dictionary.

    Returns:
        str: Command.
    '''
    cmd = 'export CONTAINER_ID=`{container_id}` && '
    cmd += 'export REPO_PATH="{repo_path}" && '
    cmd += 'export USER="{user}" && '
    cmd += 'export IMAGE="{repo}" && '
    cmd += 'export VERSION=`cat pip/version.txt` && '
    cmd += 'export STATE=`docker ps -a -f name={repo} -f status=running '
    cmd += '| grep -v CONTAINER`'
    cmd = cmd.format(
        container_id=get_container_id_command(),
        mode=info['mode'],
        repo_path=REPO_PATH,
        repo=REPO,
        user=info['user'],
    )
    return cmd


def get_remove_image_command():
    '''
    Removes docker image.

    Returns:
        str: Command.
    '''
    cmd = 'docker image rm --force {repo}'
    cmd = cmd.format(repo=REPO)
    return cmd


def get_remove_container_command():
    '''
    Removes docker container.

    Returns:
        str: Command.
    '''
    cmd = 'docker container rm --force {repo}'
    cmd = cmd.format(repo=REPO)
    return cmd


def get_requirements_command(info):
    '''
    Writes a pip frozen requirements command to docker directory.

    Args:
        info (dict): Info dictionary.

    Returns:
        str: Command.
    '''
    cmd = '{exec} zsh -c "python3.7 -m pip list --format freeze > '
    cmd += '/home/ubuntu/{repo}/docker/frozen_requirements.txt"'
    cmd = cmd.format(
        repo=REPO,
        exec=get_docker_exec_command(),
        user=info['user'],
    )
    return cmd


def get_state_command():
    '''
    Gets the state of the app.

    * Container states include: absent, running, stopped.
    * Image states include: present, absent.

    Returns:
        str: Command
    '''
    cmd = 'export IMAGE_EXISTS=`docker images {repo} | grep -v REPOSITORY` && '
    cmd += 'export CONTAINER_EXISTS=`docker ps -a -f name={repo}'
    cmd += ' | grep -v CONTAINER` && '
    cmd += 'export RUNNING=`docker ps -a -f name={repo} -f status=running '
    cmd += '| grep -v CONTAINER` && '
    cmd += 'if [ -z "$IMAGE_EXISTS" ]; then'
    cmd += '    export IMAGE_STATE="{red}absent{clear}"; '
    cmd += 'else export IMAGE_STATE="{green}present{clear}"; fi; '
    cmd += 'if [ -z "$CONTAINER_EXISTS" ]; then'
    cmd += '    export CONTAINER_STATE="{red}absent{clear}"; '
    cmd += 'elif [ -z "$RUNNING" ]; then '
    cmd += '    export CONTAINER_STATE="{red}stopped{clear}"; '
    cmd += 'else'
    cmd += '    export CONTAINER_STATE="{green}running{clear}"; '
    cmd += 'fi && '
    cmd += 'echo "app: {cyan}{repo}{clear}  -  '
    cmd += 'image: $IMAGE_STATE  -  container: $CONTAINER_STATE  -  '
    cmd += 'version: {cyan}`cat pip/version.txt`{clear}"'
    cmd = cmd.format(
        repo=REPO,
        cyan='\033[0;36m',
        red='\033[0;31m',
        green='\033[0;32m',
        clear='\033[0m',
    )
    return cmd


def get_start_command(info):
    '''
    Starts up container.

    Args:
        info (dict): Info dictionary.

    Returns:
        str: Fully resolved docker compose up command.
    '''
    cmd = 'if [ -z "$STATE" ]; then cd docker; {compose} up --detach; cd ..; fi && '
    cmd += "export CONTAINER_ID=`docker ps -a --filter name=shekels --format '{pattern}'`"
    cmd = cmd.format(
        compose=get_docker_compose_command(info),
        pattern='{{.ID}}',
    )
    return cmd


def get_stop_command(info):
    '''
    Shuts down container.

    Args:
        info (dict): Info dictionary.

    Returns:
        str: Fully resolved docker compose down command.
    '''
    cmd = 'cd docker; {compose} down; cd ..'
    cmd = cmd.format(compose=get_docker_compose_command(info))
    return cmd


def get_test_command(info, skip_slow_tests=False):
    '''
    Runs pytest.

    Args:
        info (dict): Info dictionary.
        skip_slow_tests (bool, optional): If true, skips tests marked as slow.
            Default: False.

    Returns:
        str: Command.
    '''
    env = ['REPO_ENV=True']
    if skip_slow_tests:
        env.append('SKIP_SLOW_TESTS=true')

    cmd = '{exec} '
    cmd += 'pytest /home/ubuntu/{repo}/python -c /home/ubuntu/{repo}/docker/pytest.ini {args}'
    cmd = cmd.format(
        repo=REPO,
        exec=get_docker_exec_command(env_vars=env),
        args=' '.join(info['args']),
    )
    return cmd


def get_tox_command(info):
    '''
    Run tox tests.

    Args:
        info (dict): Info dictionary.

    Returns:
        str: Command.
    '''
    cmd = '{exec} zsh -c "'
    cmd += 'rm -rf /tmp/{repo} && '
    cmd += 'cp -R /home/ubuntu/{repo}/python /tmp/{repo} && '
    cmd += 'cp -R /home/ubuntu/{repo}/docker/* /tmp/{repo}/ && '
    cmd += 'cp -R /home/ubuntu/{repo}/resources /tmp/{repo}/{repo} && '
    cmd += 'cp /home/ubuntu/{repo}/pip/* /tmp/{repo}/ && '
    cmd += 'cp /home/ubuntu/{repo}/LICENSE /tmp/{repo}/ && '
    cmd += 'cp /home/ubuntu/{repo}/README.md /tmp/{repo}/ && '
    cmd += "find /tmp/{repo}/{repo}/resources -type f | grep -vE 'icon|test_' "
    cmd += "| parallel 'rm -rf {x}' && "
    cmd += 'cp -R /home/ubuntu/{repo}/templates /tmp/{repo}/{repo} && '
    cmd += "cp -R /home/ubuntu/{repo}/python/conftest.py /tmp/{repo}/ && "
    cmd += r"find /tmp/{repo} | grep -E '__pycache__|\.pyc$' | "
    cmd += "parallel 'rm -rf' && "
    cmd += 'cd /tmp/{repo} && tox'
    cmd += '"'
    cmd = cmd.format(
        x='{}',
        repo=REPO,
        exec=get_docker_exec_command(env_vars=[]),
    )
    return cmd


def get_update_version_command(info):
    '''
    Updates version in version.txt file.

    Args:
        info (dict): Info dictionary.

    Returns:
        str: Command.
    '''
    cmd = 'echo {version} > pip/version.txt'.format(version=info['args'][0])
    return cmd


def get_zsh_command():
    '''
    Opens a zsh session inside a running container.

    Returns:
        str: Command.
    '''
    cmd = "{exec} zsh".format(exec=get_docker_exec_command())
    return cmd


# DOCKER------------------------------------------------------------------------
def get_docker_command(info):
    '''
    Get misc docker command.

    Args:
        info (dict): Info dictionary.

    Returns:
        str: Command.
    '''
    cmd = 'cd docker; '
    cmd += 'REPO_PATH="{repo_path}" USER="{user}" IMAGE="{repo}"; '
    cmd += 'docker {mode} {args} '
    cmd += 'cd ..'
    args = ' '.join(info['args'])
    cmd = cmd.format(
        repo=REPO,
        repo_path=REPO_PATH,
        user=info['user'],
        mode=info['mode'],
        args=args
    )
    return cmd


def get_docker_exec_command(working_directory=None, env_vars=['REPO_ENV=True']):
    '''
    Gets docker exec command.

    Args:
        working_directory (str, optional): Working directory.
        env_vars (list[str], optional): Optional environment variables.
            Default: ['REPO_ENV=True'].

    Returns:
        str: Command.
    '''
    cmd = 'docker exec --interactive --tty --user ubuntu:ubuntu -e {env} '
    if env_vars is not None and len(env_vars) > 0:
        cmd += '-e ' + ' -e '.join(env_vars) + ' '
    if working_directory is not None:
        cmd += '-w {} '.format(working_directory)
    cmd += '$CONTAINER_ID '
    cmd = cmd.format(
        env='PYTHONPATH="${PYTHONPATH}:' + '/home/ubuntu/{}/python" '.format(REPO),
        container_command=get_container_id_command(),
    )
    return cmd


def get_docker_compose_command(info):
    '''
    Gets docker compose command.

    Args:
        info (dict): Info dictionary.

    Returns:
        str: Command.
    '''
    cmd = 'docker compose -p {repo} -f {compose_path} '
    cmd = cmd.format(
        repo=REPO,
        repo_path=REPO_PATH,
        user=info['user'],
        compose_path=info['compose_path'],
    )
    return cmd


# MAIN--------------------------------------------------------------------------
def main():
    '''
    Print different commands to stdout depending on mode provided to command.
    '''
    info = get_info()
    mode = info['mode']
    cmds = [get_variables_command(info)]

    if mode == 'app':
        cmds.extend([
            get_start_command(info),
            get_app_command(),
        ])

    elif mode == 'build':
        cmds = [get_build_image_command()]

    elif mode == 'build-prod':
        cmds.extend([
            get_build_production_image_command(),
        ])

    elif mode == 'container':
        cmds.extend([
            get_start_command(info),
            get_container_id_command(),
        ])

    elif mode == 'coverage':
        cmds.extend([
            get_start_command(info),
            get_coverage_command(info),
        ])

    elif mode == 'destroy':
        cmds = [
            get_stop_command(info),
            get_remove_container_command(),
            get_remove_image_command(),
        ]

    elif mode == 'destroy-prod':
        cmds = [get_destroy_production_container_command()]

    elif mode == 'docs':
        cmds.extend([
            get_start_command(info),
            get_docs_command(),
        ])

    elif mode == 'fast-test':
        cmds.extend([
            get_start_command(info),
            get_test_command(info, skip_slow_tests=True),
        ])

    elif mode == 'full-docs':
        cmds.extend([
            get_start_command(info),
            get_docs_command(),
            get_coverage_command(info),
            get_architecture_diagram_command(),
            get_radon_metrics_command(),
        ])

    elif mode == 'image':
        cmds.extend([
            get_start_command(info),
            get_image_id_command(),
        ])

    elif mode == 'lab':
        cmds.extend([
            get_start_command(info),
            get_lab_command(),
        ])

    elif mode == 'lint':
        cmds.extend([
            get_start_command(info),
            'echo LINTING',
            get_lint_command(),
            'echo',
            'echo "TYPE CHECKING"',
            get_type_checking_command(),
        ])

    elif mode == 'package':
        cmds.extend([
            get_start_command(info),
            get_package_command(),
        ])

    elif mode == 'prod':
        if info['args'] == ['']:
            cmd = 'echo "Please provide a directory to map into the container '
            cmd += 'after the -a flag."'
            cmds = [cmd]
        else:
            cmds.extend([
                get_remove_pycache_command(),
                get_destroy_production_container_command(),
                get_build_production_image_command(),
                get_production_container_command(info),
            ])

    elif mode == 'publish':
        cmds.extend([
            get_start_command(info),
            get_tox_command(info),
            get_remove_pycache_command(),
            get_package_command(),
            get_publish_command(),
        ])

    elif mode == 'push':
        cmds.extend([
            get_start_command(info),
            get_push_to_dockerhub_command(info),
        ])

    elif mode == 'python':
        cmds.extend([
            get_start_command(info),
            get_python_command(),
        ])

    elif mode == 'remove':
        cmds = [get_remove_container_command()]

    elif mode == 'restart':
        cmds.extend([
            get_stop_command(info),
            get_start_command(info),
        ])

    elif mode == 'requirements':
        cmds.extend([
            get_start_command(info),
            get_requirements_command(info),
        ])

    elif mode == 'start':
        cmds.extend([
            get_start_command(info),
        ])

    elif mode == 'state':
        cmds.extend([
            get_state_command(),
        ])

    elif mode == 'stop':
        cmds.extend([
            get_stop_command(info),
        ])

    elif mode == 'test':
        cmds.extend([
            get_start_command(info),
            get_test_command(info),
        ])

    elif mode == 'tox':
        cmds.extend([
            get_start_command(info),
            get_tox_command(info),
        ])

    elif mode == 'version':
        cmds.extend([
            get_start_command(info),
        ])
        if info['args'] == ['']:
            cmds = ['echo "Please provide a version after the -a flag."']
        else:
            cmds.append(get_update_version_command(info))
            info['args'] = ['']
            cmds.extend([
                'echo LINTING',
                get_lint_command(),
                'echo',
                'echo "TYPE CHECKING"',
                get_type_checking_command(),
                get_docs_command(),
                get_coverage_command(info),
                get_architecture_diagram_command(),
                get_radon_metrics_command(),
                get_requirements_command(info),
            ])

    elif mode == 'zsh':
        cmds.extend([
            get_start_command(info),
            get_zsh_command(),
        ])

    # print is used instead of execute because REPO_PATH and USER do not
    # resolve in a subprocess and subprocesses do not give real time stdout.
    # So, running `command up` will give you nothing until the process ends.
    # `eval "[generated command] $@"` resolves all these issues.
    cmds = [
        'export CWD=`pwd`',
        'cd {}'.format(REPO_PATH)
    ] + cmds
    cmds.append('cd $CWD')
    cmd = ' && '.join(cmds)
    print(cmd)


if __name__ == '__main__':
    main()
