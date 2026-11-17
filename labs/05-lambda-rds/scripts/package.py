#!/usr/bin/env python3
"""Lab 05 · Build the Lambda package: your code + the pg8000 driver + the RDS certificates.

    python labs/05-lambda-rds/scripts/package.py

Creates:
    labs/05-lambda-rds/build/          the folder CloudFormation and the CDK deploy
    labs/05-lambda-rds/function.zip    the same files, to upload in the Lambda console
                                       (Code -> Upload from -> .zip file)
"""

import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
SRC = LAB / "src"
BUILD = LAB / "build"
ZIP = LAB / "function.zip"

# Amazon RDS certificate authorities for every Region. The function verifies the
# database's certificate against this file, so nobody can pretend to be your database.
RDS_CA_URL = "https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem"


def main():
    shutil.rmtree(BUILD, ignore_errors=True)
    BUILD.mkdir()

    print("1/4 Copying your code")
    shutil.copy2(SRC / "lambda_function.py", BUILD)

    print("2/4 Installing the driver from requirements.txt")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--quiet",
            "--target",
            str(BUILD),
            "-r",
            str(SRC / "requirements.txt"),
        ],
        check=True,
    )

    print("3/4 Downloading the RDS certificate bundle")
    try:
        with urllib.request.urlopen(RDS_CA_URL, timeout=30) as response:
            (BUILD / "global-bundle.pem").write_bytes(response.read())
    except OSError as err:
        sys.exit(
            f"Could not download {RDS_CA_URL} ({err}).\n"
            f"Open it in a browser, save it as {BUILD / 'global-bundle.pem'}, then run this script again."
        )

    print("4/4 Zipping")
    ZIP.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(BUILD.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(BUILD))

    size_kb = ZIP.stat().st_size / 1024
    print(f"\nCreated {ZIP} ({size_kb:.0f} KB).")
    print("Console: Lambda -> Code -> Upload from -> .zip file")
    print("CloudFormation / CDK: they deploy the build/ folder automatically.")


if __name__ == "__main__":
    main()
