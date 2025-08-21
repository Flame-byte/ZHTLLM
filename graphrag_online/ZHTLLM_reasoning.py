import argparse
import asyncio
import os
import re
import sys
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional

try:
    import yaml
except ImportError:
    print("PyYAML is not installed. Please install it by running: pip install pyyaml")
    sys.exit(1)


# --- Path Setup ---
# Ensure project modules can be found
workspace_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(workspace_root))
sys.path.insert(0, str(workspace_root / "graphrag_online"))

# --- Project Imports ---
from ZHTLLM_online_build import run_online_pipeline, initialize_project
from ragtest.all_output_search import run_multi_folder_search

# --- Configuration ---
# Define the root directory for all GraphRAG operations (input, output, etc.)
RAG_ROOT = str(workspace_root / "graphrag_online")
LOCK_FILE_PATH = Path(RAG_ROOT) / "ragtest" / ".lock"

# Use a thread-safe lock for in-process safety, though the file handles cross-process safety
build_lock = Lock()


def get_project_root(name: Optional[str], rag_root_base: str) -> str:
    """
    Determines the project root directory.
    - If a name is provided, it points to 'history/<name>'.
    - If no name is provided, it defaults to the 'ragtest' directory.
    """
    if name:
        return str(Path(rag_root_base) / "history" / name)
    return str(Path(rag_root_base) / "ragtest")


def run_init(name: str):
    """
    Initializes a new project programmatically.

    Args:
        name (str): The name for the new project.

    Raises:
        ValueError: If the project name is invalid or already exists.
    """
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        raise ValueError("Project name must contain only English letters, numbers, hyphens, and underscores.")

    project_root = get_project_root(name, RAG_ROOT)
    if Path(project_root).exists():
        raise ValueError(f"Project '{name}' already exists.")

    initialize_project(name, RAG_ROOT)
    return f"Successfully initialized project '{name}'."



def update_inference_settings(args, ragtest_root):
    """Updates the settings.yaml based on command-line arguments."""
    settings_path = Path(ragtest_root) / "settings.yaml"

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Could not find settings file at {settings_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading YAML from {settings_path}: {e}")
        sys.exit(1)

    # --- Set default values based on ragtest/settings.yaml ---
    settings["llm"] = settings.get("llm", {})
    settings["llm"].update({
        "model_supports_json": True,
        "max_tokens": 4096,
        "request_timeout": 180.0,
        "max_retry_wait": 20.0,
        "concurrent_requests": 1,
        "temperature": 0.6,
        "top_p": 0.9,
    })

    settings["chunks"] = settings.get("chunks", {})
    settings["chunks"]["size"] = 300

    settings["storage"] = settings.get("storage", {})
    settings["storage"]["base_dir"] = "output/${timestamp}/artifacts"
    
    settings["reporting"] = settings.get("reporting", {})
    settings["reporting"]["base_dir"] = "output/${timestamp}/artifacts"

    settings["summarize_descriptions"] = settings.get("summarize_descriptions", {})
    settings["summarize_descriptions"]["max_length"] = 1000

    settings["snapshots"] = settings.get("snapshots", {})
    settings["snapshots"]["graphml"] = True

    settings["local_search"] = settings.get("local_search", {}) or {}
    settings["local_search"].update({
        "llm_temperature": 0.6,
        "llm_top_p": 0.9,
    })

    settings["global_search"] = settings.get("global_search", {}) or {}
    settings["global_search"].update({
        "llm_temperature": 0.6,
        "llm_top_p": 0.9,
    })
    # --- End of default values ---

    if "llm" not in settings:
        settings["llm"] = {}

    if args.inference_mode == "local":
        print(f"Configuring for local inference using model '{args.local_model}'...")
        settings["llm"]["type"] = "openai_chat"
        settings["llm"]["api_base"] = args.local_api_base
        settings["llm"]["model"] = args.local_model
        settings["llm"]["api_key"] = "local"
        settings["llm"]["max_retries"] = 10000

    elif args.inference_mode == "cloud":
        print(f"Configuring for cloud inference using model '{args.cloud_model}'...")
        if not args.cloud_api_key:
            print("Error: --cloud-api-key is required for cloud inference mode.")
            sys.exit(1)

        os.environ["GRAPHRAG_API_KEY"] = args.cloud_api_key
        print("Set GRAPHRAG_API_KEY environment variable.")

        settings["llm"]["type"] = "openai_chat"
        settings["llm"]["api_base"] = args.cloud_api_base
        settings["llm"]["model"] = args.cloud_model
        settings["llm"]["api_key"] = "${GRAPHRAG_API_KEY}"
        settings["llm"]["max_retries"] = 100

    # Update embedding settings
    if "embeddings" not in settings:
        settings["embeddings"] = {}
    if "llm" not in settings["embeddings"]:
        settings["embeddings"]["llm"] = {}
    
    settings["embeddings"]["llm"]["model"] = args.embedding_model
    settings["embeddings"]["llm"]["api_base"] = args.embedding_api_base

    # Update input settings to point to the correct archive directory
    if "input" not in settings:
        settings["input"] = {}
    settings["input"]["base_dir"] = "input_new"

    try:
        with open(settings_path, "w", encoding="utf-8") as f:
            yaml.dump(settings, f, sort_keys=False, indent=2)
        print(f"Successfully updated {settings_path} for {args.inference_mode} mode.")
    except Exception as e:
        print(f"Error writing YAML to {settings_path}: {e}")
        sys.exit(1)


def add_inference_args(parser):
    """Adds shared inference arguments to the given parser."""
    inference_group = parser.add_argument_group("Inference Configuration")
    inference_group.add_argument(
        "--inference-mode",
        choices=["local", "cloud"],
        default="local",
        help='Select inference mode: "local" for a local model, "cloud" for a cloud API.',
    )
    inference_group.add_argument(
        "--cloud-api-base",
        type=str,
        default="https://api.agicto.cn/v1",
        help="The base URL for the cloud API. Used when --inference-mode=cloud.",
    )
    inference_group.add_argument(
        "--cloud-api-key",
        type=str,
        default="sk-ajs9XLA2QW1G6EbzolNq5OxOiKpkFjD7a5htM56HCrAGVHZF",
        help="The API key for the cloud API. Used when --inference-mode=cloud.",
    )
    inference_group.add_argument(
        "--cloud-model",
        type=str,
        default="deepseek-chat",
        help="The model name to use for cloud inference.",
    )
    inference_group.add_argument(
        "--local-api-base",
        type=str,
        default="http://localhost:11434/v1/",
        help="The base URL for the local inference server.",
    )
    inference_group.add_argument(
        "--local-model",
        type=str,
        default="llama3.2",
        help="The model name to use for local inference.",
    )
    inference_group.add_argument(
        "--embedding-model",
        type=str,
        default="nomic-embed-text",
        help="The model name for embeddings.",
    )
    inference_group.add_argument(
        "--embedding-api-base",
        type=str,
        default="http://localhost:11434/api",
        help="The base URL for the embedding model API.",
    )


def run_build(
    dialogue: Optional[str] = None,
    speakers: Optional[Dict[str, str]] = None,
    text_files: Optional[List[str]] = None,
    name: Optional[str] = None,
    **kwargs,
):
    """
    Runs the build process programmatically.

    Args:
        dialogue (str, optional): Path to the main dialogue audio file.
        speakers (dict, optional): A dictionary mapping speaker names to their audio file paths.
        text_files (list[str], optional): A list of paths to additional .txt files.
        name (str, optional): The name of the project to build.
        **kwargs: Additional keyword arguments for inference configuration.
    """
    async def build_async():
        # Validation
        if not dialogue and not text_files:
                return "Error: Build command requires either audio files (dialogue and speakers) or text files."
        if dialogue and not speakers:
                return "Error: --speakers are required when --dialogue is provided."

        # Determine the project root directory
        project_root = get_project_root(name, RAG_ROOT)
        print(f"Targeting project directory: {project_root}")

        # Create an args-like object for settings update
        args_dict = {
            "inference_mode": "local",
            "local_api_base": "http://localhost:11434/v1/",
            "local_model": "llama3.2",
            "cloud_api_base": "https://api.agicto.cn/v1",
            "cloud_api_key": "sk-ajs9XLA2QW1G6EbzolNq5OxOiKpkFjD7a5htM56HCrAGVHZF",
            "cloud_model": "deepseek-chat",
            "embedding_model": "nomic-embed-text",
            "embedding_api_base": "http://localhost:11434/api",
        }
        args_dict.update(kwargs)
        args = argparse.Namespace(**args_dict)
        update_inference_settings(args, project_root)

        # Core build logic
        lock_file = Path(project_root) / ".lock"
        if lock_file.exists():
                return "A build process is already running. Please wait for it to complete."

        if not build_lock.acquire(blocking=False):
                return "A build process is already running in this process."

        try:
            lock_file.touch()
            print("Build process started. Search is temporarily disabled.")
            
            await run_online_pipeline(
                dialogue_audio_path=dialogue,
                speaker_samples=speakers,
                text_file_paths=text_files,
                rag_root=project_root,
            )
            return "Build process finished successfully."
        except Exception as e:
                # Capture the full traceback for better debugging in the GUI
                import traceback
                tb_str = traceback.format_exc()
                error_message = f"An error occurred during the build process: {e}\n{tb_str}"
                print(error_message)
                return error_message
        finally:
            if lock_file.exists():
                lock_file.unlink()
            build_lock.release()
            print("Build process finished. Search is now enabled.")

    return asyncio.run(build_async())


def run_search(query: str, name: Optional[str] = None, **kwargs):
    """
    Runs the search process programmatically.

    Args:
        query (str): The search query.
        name (str, optional): The name of the project to search.
        **kwargs: Additional keyword arguments for search and inference configuration.
    """
    # Determine the project root directory
    project_root = get_project_root(name, RAG_ROOT)
    print(f"Targeting project directory: {project_root}")

    # Create an args-like object for settings update
    args_dict = {
        "method": "local",
        "level": 2,
        "response_type": "multiple paragraphs",
        "inference_mode": "local",
        "local_api_base": "http://localhost:11434/v1/",
        "local_model": "llama3.2",
        "cloud_api_base": "https://api.agicto.cn/v1",
        "cloud_api_key": "sk-ajs9XLA2QW1G6EbzolNq5OxOiKpkFjD7a5htM56HCrAGVHZF",
        "cloud_model": "deepseek-chat",
        "embedding_model": "nomic-embed-text",
        "embedding_api_base": "http://localhost:11434/api",
    }
    args_dict.update(kwargs)
    args = argparse.Namespace(**args_dict)
    update_inference_settings(args, project_root)

    # Core search logic
    lock_file = Path(project_root) / ".lock"
    if lock_file.exists():
        return "Cannot perform search: a build process is currently in progress. Please try again later."

    print("Performing search...")
    # Redirect stdout to capture the result from run_multi_folder_search
    from io import StringIO
    import sys
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()

    try:
        # We need to run the async search function in its own event loop
        # since this function is called from a non-async context (the QThread worker).
        asyncio.run(
            run_multi_folder_search(
                root_dir=project_root,
                query=query,
                community_level=args.level,
                response_type=args.response_type,
                search_method=args.method,
                config_filepath=str(Path(project_root) / "settings.yaml"),
            )
        )
    except Exception as e:
        import traceback
        tb_str = traceback.format_exc()
        # Restore stdout before printing the error to the console
        sys.stdout = old_stdout
        error_message = f"An error occurred during search: {e}\n{tb_str}"
        print(error_message)
        return error_message
    finally:
        # Ensure stdout is always restored
        sys.stdout = old_stdout

    result = captured_output.getvalue()
    print(f"Search process returned result of length {len(result)}.")
    return result


def handle_build(args):
    """
    Handles the 'build' command from the CLI.
    """
    kwargs = vars(args)
    dialogue = kwargs.pop("dialogue", None)
    speaker_names = kwargs.pop("speaker_names", None)
    speaker_paths = kwargs.pop("speaker_paths", None)
    text_files = kwargs.pop("text_files", None)
    kwargs.pop("func", None)
    name = kwargs.pop("name", None)

    speakers_dict = None
    if speaker_names and speaker_paths:
        if len(speaker_names) != len(speaker_paths):
            print(
                f"Error: The number of speaker names ({len(speaker_names)}) does not match the number of speaker paths ({len(speaker_paths)}). Audio processing will be skipped."
            )
        else:
            speakers_dict = dict(zip(speaker_names, speaker_paths))
    elif speaker_paths:
        print(
            "Warning: --speaker-names not provided. Generating speaker names from filenames."
        )
        speakers_dict = {Path(p).stem: p for p in speaker_paths}
    elif speaker_names and not speaker_paths:
        print(
            "Error: --speaker-names provided without --speaker-paths. Audio processing will be skipped."
    )

    run_build(dialogue=dialogue, speakers=speakers_dict, text_files=text_files, name=name, **kwargs)


def handle_search(args):
    """
    Handles the 'search' command from the CLI.
    """
    kwargs = vars(args)
    query = kwargs.pop("query")
    kwargs.pop("func", None)
    name = kwargs.pop("name", None)
    run_search(query, name=name, **kwargs)


def handle_init(args):
    """
    Handles the 'init' command from the CLI.
    """
    try:
        result = run_init(args.name)
        print(result)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def configure_build_parser(subparsers):
    """Configures the 'build' command parser."""
    build_parser = subparsers.add_parser(
        "build", help="Process new audio files and build the knowledge graph."
    )
    build_parser.add_argument(
        "--name",
        type=str,
        required=False,
        help="The name of the project to build. If not provided, defaults to the main 'ragtest' directory.",
    )
    build_parser.add_argument(
        "--dialogue",
        type=str,
        required=False,
        help="Path to the main dialogue audio file (e.g., 'meeting.wav').",
    )
    build_parser.add_argument(
        "--speaker-names",
        nargs="+",
        type=str,
        required=False,
        help="A list of speaker names (e.g., 'Alice' 'Bob'). If provided, must have same number of items as --speaker-paths.",
    )
    build_parser.add_argument(
        "--speaker-paths",
        nargs="+",
        type=str,
        required=False,
        help="A list of paths to speaker audio files. If --speaker-names is not provided, names will be generated from filenames.",
    )
    build_parser.add_argument(
        "--text-files",
        nargs="+",
        type=str,
        required=False,
        help="One or more paths to .txt files to include in the build.",
    )
    add_inference_args(build_parser)
    build_parser.set_defaults(func=handle_build)


def configure_search_parser(subparsers):
    """Configures the 'search' command parser."""
    search_parser = subparsers.add_parser(
        "search", help="Search the existing knowledge graph."
    )
    search_parser.add_argument(
        "-q", "--query", type=str, required=True, help="The search query to execute."
    )
    search_parser.add_argument(
        "--name",
        type=str,
        required=False,
        help="The name of the project to search. If not provided, defaults to the main 'ragtest' directory.",
    )
    search_parser.add_argument(
        "--method",
        type=str,
        default="local",
        choices=["local", "global"],
        help="The search method to use ('local' or 'global'). Default: local.",
    )
    search_parser.add_argument(
        "--level",
        type=int,
        default=2,
        help="The community level for the search. Default: 2.",
    )
    search_parser.add_argument(
        "--response_type",
        type=str,
        default="multiple paragraphs",
        help="The desired format for the response. Default: 'multiple paragraphs'.",
    )
    add_inference_args(search_parser)
    search_parser.set_defaults(func=handle_search)


def configure_init_parser(subparsers):
    """Configures the 'init' command parser."""
    init_parser = subparsers.add_parser(
        "init", help="Initialize a new project in the 'history' directory."
    )
    init_parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="The name for the new project (English letters, numbers, hyphens, underscores only).",
    )
    init_parser.set_defaults(func=handle_init)


def main():
    """
    Main entry point for the ZHTLLM reasoning script.
    """
    parser = argparse.ArgumentParser(
        description="ZHTLLM Reasoning Engine: Build knowledge graphs from audio or search them."
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- Configure Parsers ---
    configure_init_parser(subparsers)
    configure_build_parser(subparsers)
    configure_search_parser(subparsers)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
