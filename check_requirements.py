
import json
import re
import sys
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE_URL = "https://pypi.org/pypi"
TIMEOUT = 15


def get_json(url):
    """Return (data, status_code), treating HTTP 404 as not found."""
    request = Request(
        url,
        headers={"Accept": "application/json",
                 "User-Agent": "PyPI-Requirements-Checker/1.0"},
    )

    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            return json.load(response), response.status
    except HTTPError as exc:
        if exc.code == 404:
            return None, 404
        raise


def parse_requirement(line):
    """Parse a pinned requirement such as requests==2.31.0."""
    line = line.split("#", 1)[0].strip()

    if not line:
        return None

    match = re.fullmatch(
        r"([A-Za-z0-9_.-]+)\s*==\s*([^\s;]+)",
        line,
    )

    return match.groups() if match else None


def check_requirements(filename):
    with open(filename, encoding="utf-8-sig") as file:
        lines = file.readlines()

    checked = 0
    missing_packages = []
    missing_versions = []
    valid_releases = []

    for line_number, line in enumerate(lines, start=1):
        requirement = parse_requirement(line)

        # Ignore blank lines and comments.
        if not line.split("#", 1)[0].strip():
            continue

        checked += 1

        if requirement is None:
            print(
                f"Warning: unsupported requirement on line "
                f"{line_number}: {line.strip()}"
            )
            continue

        name, version = requirement
        package_url = f"{BASE_URL}/{quote(name, safe='')}/json"
        version_url = (
            f"{BASE_URL}/{quote(name, safe='')}/"
            f"{quote(version, safe='')}/json"
        )

        try:
            # Check whether the package exists.
            project, status = get_json(package_url)

            if status == 404:
                missing_packages.append(f"{name}=={version}")
                continue

            # Check whether the pinned release exists.
            release, status = get_json(version_url)

            if status == 404:
                missing_versions.append(f"{name}=={version}")
                continue

            # Use upload_time from the first file in urls.
            urls = release.get("urls", [])

            if not urls or not urls[0].get("upload_time"):
                print(
                    f"Warning: upload time unavailable for "
                    f"{name}=={version}"
                )
                continue

            upload_time = urls[0]["upload_time"]
            year = datetime.fromisoformat(
                upload_time.replace("Z", "+00:00")
            ).year

            valid_releases.append(
                (upload_time, f"{name}=={version}({year})")
            )

        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(
                f"Warning: could not check {name}=={version}: {exc}"
            )

    print(f"1. Dependencies checked: {checked}")

    print("2. Packages not on PyPI:")
    for item in missing_packages:
        print(f"   {item}")
    if not missing_packages:
        print("   None")

    print("3. Versions not on PyPI:")
    for item in missing_versions:
        print(f"   {item}")
    if not missing_versions:
        print("   None")

    print("4. Oldest pinned release:")
    if valid_releases:
        oldest = min(valid_releases, key=lambda item: item[0])
        print(f"   {oldest[1]}")
    else:
        print("   None")


if __name__ == "__main__":
    filename = sys.argv[1] if len(sys.argv) > 1 else "requirements.txt"
    check_requirements(filename)
