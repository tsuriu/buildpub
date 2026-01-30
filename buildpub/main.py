import argparse
import os
import shutil
import sys
import tempfile
from git import Repo
import docker
from docker.errors import BuildError, APIError
from loguru import logger

def clone_repo(repo_url, branch, dest_dir):
    """Clones the repository to the destination directory."""
    logger.info(f"Cloning repository: {repo_url} (branch: {branch})")
    try:
        Repo.clone_from(repo_url, dest_dir, branch=branch)
        return True
    except Exception as e:
        logger.error(f"Failed to clone repository: {e}")
        return False

def build_image(client, context_path, dockerfile_path, full_image_name, build_args=None):
    """Builds the Docker image."""
    logger.info(f"Building image: {full_image_name} using {dockerfile_path}")
    
    # Verify Dockerfile exists
    full_dockerfile_path = os.path.join(context_path, dockerfile_path)
    if not os.path.exists(full_dockerfile_path):
            logger.error(f"Dockerfile not found at {full_dockerfile_path}")
            return False

    try:
        # Note: docker.io/docker/api/client.py build method uses 'path' for the build context
        # and 'dockerfile' for the relative path to the Dockerfile within that context.
        image, build_logs = client.images.build(
            path=context_path,
            dockerfile=dockerfile_path,
            tag=full_image_name,
            rm=True, # Remove intermediate containers
            buildargs=build_args
        )
        for chunk in build_logs:
            if 'stream' in chunk:
                logger.debug(chunk['stream'].strip())
        
        logger.success("Build successful.")
        return True
    except BuildError as e:
        logger.error("Build failed!")
        for log_line in e.build_log:
            if 'stream' in log_line:
                logger.error(log_line['stream'].strip())
        return False
    except APIError as e:
        logger.error(f"Docker API Error during build: {e}")
        return False

def push_image(client, image_name, tag):
    """Pushes the Docker image to the registry."""
    full_image_name = f"{image_name}:{tag}"
    logger.info(f"Pushing image: {full_image_name}")
    try:
        # Push returns a stream of logs
        push_logs = client.images.push(image_name, tag=tag, stream=True, decode=True)
        for chunk in push_logs:
            if 'status' in chunk:
                logger.info(f"{chunk.get('status')} {chunk.get('progress', '')}")
            if 'error' in chunk:
                logger.error(f"Push error: {chunk['error']}")
                return False
        
        logger.success(f"Successfully pushed {full_image_name}")
        return True
    except APIError as e:
        logger.error(f"Docker API Error during push: {e}")
        return False

import re
from git import InvalidGitRepositoryError

def infer_image_name(repo_url):
    """
    Infers image name from a git URL.
    Example: https://github.com/user/repo.git -> user/repo
             git@github.com:user/repo.git -> user/repo
    """
    # Remove .git suffix
    if repo_url.endswith(".git"):
        repo_url = repo_url[:-4]
    
    # Handle ssh format (git@host:user/repo)
    if ":" in repo_url and "://" not in repo_url:
        parts = repo_url.split(":", 1)
        if len(parts) == 2:
            return parts[1]
    
    # Handle http/https format
    parts = repo_url.split("/")
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    
    return None

def login_to_docker(client, username, password, registry=None):
    """Logs into a Docker registry."""
    if not username or not password:
        logger.info("Skipping login (credentials not provided).")
        return True
    
    try:
        logger.info(f"Logging in as {username}...")
        client.login(username=username, password=password, registry=registry)
        logger.success("Login successful.")
        return True
    except APIError as e:
        logger.error(f"Login failed: {e}")
        return False

def run_pipeline(repo_url=None, branch="main", image_name=None, tag="latest", dockerfile_path="Dockerfile", build_args=None, username=None, password=None, registry=None, local_path=None):
    """
    Orchestrates the build and push process.
    If local_path is provided, uses it as context and skips cloning.
    If repo_url is provided, clones it.
    """
    # Validation
    if not image_name:
        logger.error("Image name could not be determined.")
        return False

    temp_dir = None
    context_path = local_path

    try:
        # 1. Setup Docker Client
        try:
            client = docker.from_env()
        except Exception as e:
            logger.error(f"Failed to connect to Docker daemon: {e}")
            logger.error("Please ensure Docker is running.")
            return False

        # 2. Login (if creds provided)
        if not login_to_docker(client, username, password, registry):
             return False

        # 3. Prepare Context (Clone if needed)
        if not context_path:
            if not repo_url:
                logger.error("No repository URL or local path provided.")
                return False
            
            temp_dir = tempfile.mkdtemp()
            context_path = temp_dir
            if not clone_repo(repo_url, branch, temp_dir):
                return False
        else:
            logger.info(f"Using local path as build context: {context_path}")

        # 4. Build Image
        full_image_name = f"{image_name}:{tag}"
        if not build_image(client, context_path, dockerfile_path, full_image_name, build_args):
            return False

        # 5. Push Image
        if not push_image(client, image_name, tag):
            return False

        return True

    finally:
        # Cleanup
        if temp_dir:
            logger.info(f"Cleaning up temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir)

def main():
    parser = argparse.ArgumentParser(description="Clone git repo (or use local), build Docker image, and push to registry.")
    parser.add_argument("--repo", help="Git repository URL (optional if in a git repo)")
    parser.add_argument("--branch", default="main", help="Git branch to checkout (default: main). Ignored if using local dir.")
    parser.add_argument("--image", help="Target image name (e.g. username/repo). Auto-inferred if possible.")
    parser.add_argument("--tag", default="latest", help="Image tag (default: latest)")
    parser.add_argument("--dockerfile", default="Dockerfile", help="Path to Dockerfile relative to repo root (default: Dockerfile)")
    parser.add_argument("--build-arg", action='append', help="Build arguments in KEY=VALUE format", dest="build_args")
    parser.add_argument("--username", help="Docker registry username (env: DOCKER_USERNAME)")
    parser.add_argument("--password", help="Docker registry password/token (env: DOCKER_PASSWORD)")
    parser.add_argument("--registry", help="Docker registry URL (default: Docker Hub)")
    parser.add_argument("--auto-version", action="store_true", help="Automatically bump patch version based on latest git tag")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output (INFO level). Default is quiet (ERROR only).")
    
    args = parser.parse_args()

    # Configure Logging
    logger.remove()
    log_level = "INFO" if args.verbose else "ERROR"
    logger.add(sys.stderr, level=log_level)

    repo_url = args.repo
    image_name = args.image
    local_path = None
    tag = args.tag
    
    # Detect local git repo if no repo arg
    current_repo_obj = None
    if not repo_url:
        try:
            local_repo = Repo(os.getcwd())
            logger.info("Detected local git repository.")
            local_path = os.getcwd()
            current_repo_obj = local_repo
            
            # Try to get remote ID for inference
            try:
                remote_url = local_repo.remote().url
                logger.info(f"Found remote URL: {remote_url}")
                if not image_name:
                    image_name = infer_image_name(remote_url)
                    if image_name:
                        logger.info(f"Inferred image name: {image_name}")
            except ValueError:
                pass # No remote
                
        except InvalidGitRepositoryError:
             logger.error("No --repo argument provided and current directory is not a git repository.")
             sys.exit(1)
    
    # Infer image name from repo_url if not yet set
    if not image_name and repo_url:
        image_name = infer_image_name(repo_url)
        if image_name:
            logger.info(f"Inferred image name from --repo: {image_name}")

    if not image_name:
        logger.error("Could not infer image name. Please provide --image.")
        sys.exit(1)

    # Auto-version logic
    if args.auto_version:
        logger.info("Auto-versioning enabled.")
        try:
            # If we don't have a local repo object yet (remote build), we can't easily get tags *before* cloning.
            # However, for the 'Local Build' case, we have `current_repo_obj`.
            # For 'Remote Build', run_pipeline clones it. adapting run_pipeline to return or handle versioning is complex.
            # Strategy: Only support auto-version for Local or if we can peek at remote tags.
            # Simpler: If local, use local tags. If remote, git ls-remote?
            
            # Let's stick to supporting it primarily for Local Builds or if we can access the repo.
            if current_repo_obj:
                tags = sorted(current_repo_obj.tags, key=lambda t: t.commit.committed_datetime)
                if tags:
                    latest_tag = str(tags[-1])
                    logger.info(f"Latest git tag: {latest_tag}")
                    
                    # Simple semantic version bump logic
                    # Remove 'v' prefix if present
                    version_str = latest_tag.lstrip('v')
                    parts = version_str.split('.')
                    if len(parts) >= 3:
                        # Bump patch
                        try:
                            parts[-1] = str(int(parts[-1]) + 1)
                            new_version = ".".join(parts)
                            if latest_tag.startswith('v'):
                                new_version = f"v{new_version}"
                            tag = new_version
                            logger.info(f"Bumped version to: {tag}")
                        except ValueError:
                            logger.warning(f"Could not parse version {latest_tag} as semver. using default tag.")
                    else:
                         logger.warning(f"Tag {latest_tag} is not standard semantic versioning (x.y.z). Skipping bump.")
                else:
                    logger.info("No git tags found. Defaults to 'v0.0.1'?")
                    tag = "v0.0.1"
                    logger.info(f"Initial version: {tag}")
            else:
                 # TODO: Support remote tag listing (git ls-remote)
                 logger.warning("Auto-version currently only supported for local git repositories.")
                 
        except Exception as e:
            logger.error(f"Failed to auto-version: {e}")

    # Fallback to env vars
    username = args.username or os.getenv("DOCKER_USERNAME")
    password = args.password or os.getenv("DOCKER_PASSWORD")

    build_args_dict = {}
    if args.build_args:
        for arg in args.build_args:
            if '=' in arg:
                key, value = arg.split('=', 1)
                build_args_dict[key] = value
            else:
                logger.warning(f"Skipping malformed build argument: {arg}")

    success = run_pipeline(
        repo_url=repo_url,
        branch=args.branch,
        image_name=image_name,
        tag=tag,
        dockerfile_path=args.dockerfile,
        build_args=build_args_dict,
        username=username,
        password=password,
        registry=args.registry,
        local_path=local_path
    )

    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
