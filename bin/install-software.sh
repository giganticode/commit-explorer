#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

tools_dir="$DIR/../software"

if ! command -v unzip &> /dev/null
then
    echo "unzip could not be found. Trying to install it ..."
    apt-get update && apt-get install -y unzip
fi

if ! command -v unzip &> /dev/null
then
    echo "java could not be found. Trying to install it ..."
    apt-get install -y openjdk-11-jdk
    # Linux spec #TODO support macos
fi

if ! [ -d "$tools_dir" ]; then
    mkdir "$tools_dir"
fi
cd "$tools_dir"

echo "=====================>   RefactoringMiner"

rm -rf RefactoringMiner
git clone https://github.com/tsantalis/RefactoringMiner
cd RefactoringMiner
./gradlew distZip
ZIP_NAME="$(ls build/distributions)"
cd ..
unzip -o "RefactoringMiner/build/distributions/$ZIP_NAME"
rm -rf RefactoringMiner/*

unzipped=$(ls | grep -e "^RefactoringMiner-\([[:digit:]]\.[[:digit:]]\.[[:digit:]]\)\$")
VERSION=$(echo "$unzipped" | sed -n 's/RefactoringMiner-\([[:digit:]]\.[[:digit:]]\.[[:digit:]]\)/\1/p')
mv "$unzipped" RefactoringMiner
mv RefactoringMiner/"$unzipped" RefactoringMiner/"$VERSION"

echo "=====================>   GumTree"

rm -rf GumTree
curl -L https://github.com/GumTreeDiff/gumtree/releases/download/v3.0.0-beta2/gumtree-3.0.0-beta2.zip --output gumtree-3.0.0-beta2.zip
unzip gumtree-3.0.0-beta2.zip
rm -rf gumtree-3.0.0-beta2.zip
mkdir GumTree
mv gumtree-3.0.0-beta2 GumTree
mv GumTree/gumtree-3.0.0-beta2 GumTree/3.0.0-beta2

echo "=====================>   PythonParser"

rm -rf pythonparser
git clone https://github.com/GumTreeDiff/pythonparser.git
pip install -r pythonparser/requirements.txt
[[ ":$PATH:" != *":${PWD}/pythonparser:"* ]] && export PATH="${PWD}/pythonparser:${PATH}"
