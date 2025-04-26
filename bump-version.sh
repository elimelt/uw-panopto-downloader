
pyproj_t='pyproject.toml'
pyinit_t='uw_panopto_downloader/__init__.py'

# Get the current version from pyproject.toml
regex_pyproj='version = "([0-9]+.[0-9]+.[0-9]+)"'
regex_pyinit='__version__ = "([0-9]+.[0-9]+.[0-9]+)"'

pyproj_version_raw=$(grep -Eo "$regex_pyproj" "$pyproj_t")
pyinit_version_raw=$(grep -Eo "$regex_pyinit" "$pyinit_t")

pyproj_version_extracted=$(echo "$pyproj_version_raw" | grep -Eo '[0-9]+.[0-9]+.[0-9]+')
pyinit_version_extracted=$(echo "$pyinit_version_raw" | grep -Eo '[0-9]+.[0-9]+.[0-9]+')

echo "Current version in $pyproj_t: $pyproj_version_extracted"
echo "Current version in $pyinit_t: $pyinit_version_extracted"

# assert that the versions are the same
if [ "$pyproj_version_extracted" != "$pyinit_version_extracted" ]; then
    echo "Version mismatch between $pyproj_t and $pyinit_t: $pyproj_version_extracted vs $pyinit_version_extracted"
    exit 1
fi

# Increment the version
IFS='.' read -r major minor patch <<< "$pyproj_version_extracted"
if [ "$1" == "major" ]; then
    major=$((major + 1))
    minor=0
    patch=0
elif [ "$1" == "minor" ]; then
    minor=$((minor + 1))
    patch=0
elif [ "$1" == "patch" ]; then
    patch=$((patch + 1))
else
    echo "defaulting to patch version bump"
    patch=$((patch + 1))
fi
new_version="$major.$minor.$patch"

# check if --dry-run flag is set
if [ "$2" == "--dry-run" ]; then
    echo "Dry run: new version would be $new_version"
    exit 0
fi

# check for changes in the working directory
if [ -n "$(git status --porcelain)" ]; then
    echo "Working directory is not clean. Please commit or stash your changes before running this script."
    exit 1
fi



# Use platform-specific sed command
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "^s/version = \".*\"/version = \"$new_version\"/" "$pyproj_t"
    sed -i '' "^s/__version__ = \".*\"/__version__ = \"$new_version\"/" "$pyinit_t"
else
    sed -i "s/version = \".*\"/version = \"$new_version\"/" "$pyproj_t"
    sed -i "s/__version__ = \".*\"/__version__ = \"$new_version\"/" "$pyinit_t"
fi

echo "Updated version in $pyproj_t and $pyinit_t to: $new_version"

# Commit the changes
git add "$pyproj_t" "$pyinit_t"
git commit -m "Bump version to $new_version"
git tag -a "v$new_version" -m "Version $new_version"
git push origin main
git push origin "v$new_version"
echo "Pushed changes to remote repository and created tag v$new_version"
echo "Done!"