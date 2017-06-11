import os
import sys
import tempfile
import tarfile
import shutil
import subprocess

import requests

import infraboxcli.env
from infraboxcli.log import logger

def download_file(url, filename, args):
    headers = {'auth-token': args.token}
    r = requests.get(url, headers=headers, stream=True, timeout=5)

    if r.status_code == 404:
        # no file exists
        return

    if r.status_code != 200:
        logger.error("Failed to download output of job")
        sys.exit(1)

    with open(filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)

def pull(args):
    infraboxcli.env.check_env_cli_token(args)
    infraboxcli.env.check_env_project_id(args)

    headers = {'auth-token': args.token}
    url = '%s/api/v1/project/%s/job/%s/manifest' % (args.host, args.project_id, args.job_id)
    r = requests.get(url, headers=headers, timeout=5)

    if r.status_code != 200:
        logger.error("Failed to download job manifest")
        logger.error("Validate your job id and make sure you used 'keep=true' in your job definition")
        sys.exit(1)

    manifest = r.json()

    # Create directories
    path = os.path.join(tempfile.gettempdir(), 'infrabox', manifest['id'])
    if os.path.exists(path):
        shutil.rmtree(path)

    download_path = os.path.join(path, 'downloads')
    os.makedirs(download_path)
    inputs_path = os.path.join(path, 'inputs')
    os.makedirs(inputs_path)
    cache_path = os.path.join(path, 'cache')
    os.makedirs(cache_path)
    output_path = os.path.join(path, 'output')
    os.makedirs(output_path)

    # download dependencies
    for d in manifest['dependencies']:
        logger.info('Downloading output of %s' % d['name'])
        p = os.path.join(inputs_path, d['name'])
        os.makedirs(p)
        package_path = os.path.join(download_path, '%s.%s' % (d['id'], d['output']['format']))
        download_file(d['output']['url'], package_path, args)

        if not os.path.exists(package_path):
            continue

        # unpack
        tar = tarfile.open(package_path)
        tar.extractall(p)

    # remove download dir again
    shutil.rmtree(download_path)

    # pulling images
    logger.info("Pulling image")
    image = manifest['image'].replace("//", "/")
    subprocess.check_call(('docker', 'pull', image))

    logger.info("Running container")
    subprocess.check_call(('docker', 'run', '-v', '%s:/infrabox' % path, image))