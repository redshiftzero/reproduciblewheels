import fnmatch
import json
import re
import requests
import shutil
import subprocess
import tempfile
import os
import uuid

from typing import Dict, List, Tuple, Union


TOP_PACKAGES_URL = "https://hugovk.github.io/top-pypi-packages/top-pypi-packages-365-days.json"
MONITOR_LIST_TXT = "watched_packages.txt"

# Packages on FPF mirror + cryptography - THESE_DONT_BUILD_YET
ADDL_PACKAGES_TO_MONITOR = [
   "alembic", "arrow", "atomicwrites", "attrs", "certifi", "chardet", "click", "cryptography",
   "coverage", "flake8", "furl", "idna", "mako", "markupsafe", "mccabe", "more-itertools",
   "multidict", "orderedmultidict", "pathlib2", "pip-tools", "pluggy", "py", "pycodestyle",
   "pyflakes", "pytest", "pytest-cov", "pytest-random-order", "python-dateutil",
   "python-editor", "pyyaml", "redis", "requests", "securedrop-sdk", "setuptools",
   "sip", "six", "sqlalchemy", "urllib3", "vcrpy", "werkzeug", "wrapt", "yarl"]

# pyqt5: fails to build due to an error
# scipy, scikit-learn: require lapack/blas support
# enum34: build error - AttributeError: module 'enum' has no attribute 'IntFlag'
# matplotlib: got hash mismatch during build o___O
# ipython: matching logic for selecting built wheel doesn't work here due to ipython_genutils
# pandas: Excluding because it's taking forever for it to build (more than 20m)
THESE_DONT_BUILD_YET = ["pyqt5", "scipy", "enum34", "scikit-learn", "matplotlib", "ipython", "pandas"]
REGEX_SOURCE_TARBALL = r'\./[a-zA-Z0-9_.-]*\.tar\.gz'
REGEX_SHA_256_HASH = r'\b[a-f0-9]+'
SENTINEL = '<!--- CUT -->'
BUILD_TIME = "1596163658"

os.environ["SOURCE_DATE_EPOCH"] = BUILD_TIME


def get_top_100_packages(url: str) -> List[str]:
    """
    Used to generate the top 100 packages on PyPI.
    """
    req = requests.get(TOP_PACKAGES_URL)
    result = json.loads(req.text)["rows"]

    # These packages in result["rows"] are ordered
    # by download_count, so let's just take the first
    # 100.
    project_names = [result[x]["project"] for x in range(100)]
    return project_names


def update_top_packages_file() -> None:
    """
    Used to update the list of top packages, which is stored in
    watched_packages.txt.
    """
    project_names = get_top_100_packages(TOP_PACKAGES_URL)
    with open('watched_packages.txt', 'w') as f:
        f.writelines([x + '\n' for x in project_names])


def regenerate_data() -> Dict:
    reproducibility_data = {}

    with open("watched_packages.txt", "r") as f:
        popular_pkgs = f.read().splitlines()

    full_package_list = set(popular_pkgs) | set(ADDL_PACKAGES_TO_MONITOR)
    packages_to_check = full_package_list - set(THESE_DONT_BUILD_YET)

    for project in sorted(packages_to_check):
        result, hash_1, hash_2 = is_wheel_reproducible(project)
        reproducibility_data.update({project: {
                                        'result': result,
                                        'hash_1': hash_1,
                                        'hash_2': hash_2}})

    # Let's save and commit this for transparency's sake.
    with open("site_data.json", "w") as f:
        f.write(json.dumps(reproducibility_data))

    return reproducibility_data


def regenerate_site(reproducibility_data: Dict) -> None:
    """Dumb function that directly edits index.html"""
    REPRODUCIBLE = '<li class="list-group-item list-group-item-success">✅&nbsp;&nbsp;'
    NOT_REPRODUCIBLE = '<li class="list-group-item list-group-item-danger">❌&nbsp;&nbsp;'
    TERMINATOR = "</li>"

    with open("docs/index.html", "r") as f:
        site_before = f.read()

    prefix, _, postfix = site_before.split(SENTINEL)
    site_after = prefix + '\n' + SENTINEL + '\n'

    for project_name, project_data in reproducibility_data.items():
        project_link = f'<a href="https://pypi.org/project/{project_name}/">{project_name}</a>'
        if project_data['result']:
            site_after += REPRODUCIBLE + project_link + TERMINATOR + '\n'
        else:
            site_after += NOT_REPRODUCIBLE + project_link + TERMINATOR + '\n'

    site_after += '\n' + SENTINEL + '\n' + postfix

    with open("docs/index.html", "w") as f:
        f.write(site_after)


def is_wheel_reproducible(project_name: str) -> Tuple[bool, str, str]:
    """
    Build wheel twice, return a bool for reproducibility (convienient)
    as well as the hash values themselves for sharing with others.
    """

    print(f'⏳ starting reproducibility check for {project_name}')
    parent_dir = os.getcwd()

    hash_results = []
    build_dir = '/tmp/buildwheel'
    for _ in range(2):
        os.mkdir(build_dir)
        os.chdir(build_dir)

        result = subprocess.check_output(
            ['python3',
            '-m',
            'pip',
            'wheel',
            project_name,
            '--no-binary',
            ':all:',
            '--no-cache-dir',
            '--build',
            build_dir]
        )

        # A fun fact is that if the package name is foo-bar, the
        # built wheel will have the format foo_bar. So, we replace
        # - with _ for matching purposes.
        project_name_wheel = project_name.replace('-', '_')
        wheel_pattern = re.compile(fnmatch.translate(f'{project_name_wheel}*.whl'), re.IGNORECASE)
        matching_wheels = [x for x in os.listdir() if re.match(wheel_pattern, x)]

        if len(matching_wheels) != 1:
            raise RuntimeError(f'uh oh!!!!! found too few or two many wheels: {matching_wheels}')

        wheel_file_location = matching_wheels[0]
        hash_result = subprocess.check_output(['shasum', '-a', '256', wheel_file_location])
        hash_value = re.findall(REGEX_SHA_256_HASH, hash_result.decode('utf-8'))[0]
        hash_results.append(hash_value)

        os.chdir(parent_dir)
        shutil.rmtree(build_dir)

    is_reproducible = hash_results[0] == hash_results[1]
    if not is_reproducible:
        print(f'❌: package "{project_name}" is not reproducible yet')
    else:
        print(f'✅: package "{project_name}" is reproducible!')

    return is_reproducible, hash_results[0], hash_results[1]


if __name__ == "__main__":
    data = regenerate_data()
    print(data)
    regenerate_site(data)
