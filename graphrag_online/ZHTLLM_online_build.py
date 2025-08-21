import os
import sys
from pathlib import Path
import re
import asyncio
import shutil

from graphrag.index.cli import index_cli
from graphrag.index.emit.types import TableEmitterType
from graphrag.index.progress.types import ReporterType

# --- Path Setup ---
# Add required directories to sys.path for robust module imports
workspace_root = Path(__file__).resolve().parent.parent
# Add parent of 'graphrag_online' for relative imports to work
sys.path.insert(0, str(workspace_root))
# Add '3D-Speaker' directory to import the dialogue recorder
sys.path.insert(0, str(workspace_root / "3D-Speaker"))

# --- Imports from project files ---
from dialogue_recorder_2 import process_dialogue
from graphrag_online.ragtest.run_incremental_index import prepare_and_archive_files


def initialize_project(project_name: str, rag_root: str):
    """
    Initializes a new GraphRAG project in the 'history' directory.

    Args:
        project_name (str): The name for the new project.
        rag_root (str): The root directory for GraphRAG operations.
    """
    if not re.match(r"^[a-zA-Z0-9_-]+$", project_name):
        print(
            f"Error: Project name '{project_name}' contains invalid characters. "
            "Only English letters, numbers, hyphens, and underscores are allowed."
        )
        return

    history_dir = Path(rag_root) / "history"
    history_dir.mkdir(exist_ok=True)

    project_path = history_dir / project_name

    if project_path.exists():
        print(f"Error: Project '{project_name}' already exists at '{project_path}'.")
        return

    print(f"Initializing new project '{project_name}' at '{project_path}'...")

    initialization_successful = False
    try:
        index_cli(
            root_dir=str(project_path),
            init=True,
            verbose=False,
            reporter=ReporterType.RICH,
            # --- Defaults for init ---
            resume="",
            update_index_id=None,
            memprofile=False,
            nocache=False,
            config_filepath=None,
            emit=[],
            dryrun=False,
            skip_validations=False,
            output_dir=None,
        )
        initialization_successful = True
    except SystemExit as e:
        # A 0 or None exit code from sys.exit() is considered a success
        if e.code == 0 or e.code is None:
            initialization_successful = True
        else:
            print(f"GraphRAG initialization failed with exit code {e.code}.")
    except Exception as e:
        print(f"An error occurred during project initialization: {e}")

    if initialization_successful:
        print(f"Project '{project_name}' core files initialized.")
        try:
            (project_path / "input_new").mkdir(exist_ok=True)
            (project_path / "input_archive").mkdir(exist_ok=True)
            print("Created 'input_new' and 'input_archive' directories.")
            
            # --- MODIFICATION: Replace prompts with Chinese versions ---
            source_prompt_dir = workspace_root / "Chinese_prompt"
            target_prompt_dir = project_path / "prompts"
            
            if source_prompt_dir.exists() and target_prompt_dir.exists():
                print(f"Replacing prompts in '{target_prompt_dir}' with Chinese prompts.")
                for item in source_prompt_dir.iterdir():
                    if item.is_file():
                        shutil.copy2(item, target_prompt_dir / item.name)
                print("Successfully replaced prompt files.")
            else:
                if not source_prompt_dir.exists():
                    print(f"Warning: Source prompt directory not found at '{source_prompt_dir}'")
                if not target_prompt_dir.exists():
                    print(f"Warning: Target prompt directory not found at '{target_prompt_dir}'")
            # --- END MODIFICATION ---

        except OSError as e:
            print(f"Error creating subdirectories: {e}")


async def run_online_pipeline(
    rag_root: str,
    dialogue_audio_path: str = None,
    speaker_samples: dict[str, str] = None,
    text_file_paths: list[str] = None,
):
    """
    Runs the full online pipeline:
    1. Converts audio dialogue to a text file using speaker diarization (if provided).
    2. Gathers all text files (from audio conversion and direct input).
    3. Archives the generated text files for incremental indexing.
    4. Runs the GraphRAG indexing process.

    Args:
        rag_root (str): The root directory for GraphRAG operations.
        dialogue_audio_path (str, optional): Path to the main dialogue audio file.
        speaker_samples (dict, optional): A dictionary mapping speaker names to their audio file paths.
        text_file_paths (list[str], optional): Paths to additional .txt files.
    """
    ragtest_path = Path(rag_root)
    all_text_files_to_process = []

    # Initialize provided text files if they exist
    if text_file_paths:
        all_text_files_to_process.extend(text_file_paths)
        print(f"Received {len(text_file_paths)} text file(s) to process.")

    # --- 1. Audio to Text Conversion (if audio is provided) ---
    if dialogue_audio_path and speaker_samples:
        print("\n--- Step 1: Converting Audio to Text ---")
        dialogue_audio_file = Path(dialogue_audio_path)
        print(f"Starting pipeline with dialogue from '{dialogue_audio_file.name}' and GraphRAG root at '{ragtest_path}'")

        # The speaker name (key) is derived from the sample's filename stem
        # speaker_samples is now the dictionary we need

        # Validate that all provided audio files exist
        all_audio_files = [dialogue_audio_file] + [Path(p) for p in speaker_samples.values()]
        files_exist = True
        for f_path in all_audio_files:
            if not f_path.exists():
                print(f"Error: Audio file not found at '{f_path}'")
                files_exist = False
        
        if not files_exist or not speaker_samples:
            print("Audio processing aborted due to missing files.")
        else:
            print(f"Found dialogue file: {dialogue_audio_file.name}")
            print(f"Found {len(speaker_samples)} speaker sample(s): {list(speaker_samples.keys())}")

            output_txt_dir = ragtest_path / "temp_transcripts"
            output_txt_dir.mkdir(exist_ok=True)
            output_txt_path = output_txt_dir / f"{dialogue_audio_file.stem}_transcript.txt"

            try:
                process_dialogue(
                    total_audio_path=str(dialogue_audio_file),
                    speaker_samples=speaker_samples,
                    output_filepath=str(output_txt_path)
                )
            except Exception as e:
                if "modelscope" in str(e) or "transformers" in str(e):
                    error_msg = (
                        "Audio processing failed due to missing or conflicting packages.\n"
                        "Please ensure 'modelscope', 'funasr', 'torch', and 'transformers' are correctly installed.\n"
                        f"Original error: {e}"
                    )
                    raise RuntimeError(error_msg) from e
                else:
                    raise e

            print(f"Dialogue transcript saved to: {output_txt_path}")
            all_text_files_to_process.append(str(output_txt_path))

    # --- 2. Archive the new text file ---
    if not all_text_files_to_process:
        print("\nNo text files to process. Aborting pipeline.")
        return

    print("\n--- Step 2: Archiving Text File for Indexing ---")
    prepare_and_archive_files(
        file_paths=all_text_files_to_process,
        root_dir=rag_root  # Pass the correct root directory here
    )

    # --- 3. Run GraphRAG Indexing ---
    print("\n--- Step 3: Running GraphRAG Indexing ---")
    try:
        # NOTE: We run indexing in a subprocess because the GraphRAG library
        # uses signal handlers that can only be registered on the main thread.
        # Running in a worker thread inside the GUI would cause a crash.
        command = [
            sys.executable,  # Use the same python that's running the GUI
            "-m",
            "graphrag.index",
            "--root",
            rag_root,
            "--reporter",
            "rich",  # Corresponds to ReporterType.RICH
            "--emit",
            "parquet",  # Corresponds to TableEmitterType.Parquet
        ]

        print(f"Running indexing command: {' '.join(command)}")

        # Create a new environment for the subprocess, ensuring it has the correct PYTHONPATH
        # This resolves ModuleNotFoundError when graphrag is not found in the subprocess
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(sys.path)

        process = await asyncio.create_subprocess_exec(
            *command,
            # By not specifying stdout and stderr, they will be inherited from the parent
            # and printed directly to the terminal in real-time.
            env=env
        )

        await process.wait()

        if process.returncode != 0:
            output = (
                f"GraphRAG indexing failed with return code {process.returncode}\n"
                "Please check the terminal output above for detailed error messages."
            )
            print(output)
            raise RuntimeError("GraphRAG indexing failed.")
        else:
            print("GraphRAG indexing process finished successfully.")

    except Exception as e:
        print(f"An error occurred during GraphRAG indexing: {e}")
        # Re-raise to be caught by the worker thread handler
        raise


if __name__ == "__main__":
    # This example demonstrates how to call the main pipeline function.
    
    print("--- Running ZHTLLM Online Pipeline ---")

    # --- Configuration: Update these paths to match your files ---
    # Path to the main dialogue audio file (e.g., a meeting recording).
    DIALOGUE_AUDIO_PATH = "/home/qin/ZHTLLM/3D-Speaker/Audio-Text/audio/combined.wav"
    
    # A list of paths to the audio samples for each speaker.
    # The filename (without extension) will be used as the speaker's name.
    # For example, 'speaker-1.wav' will identify 'speaker-1'.
    SPEAKER_SAMPLE_PATHS = [
        "/home/qin/ZHTLLM/3D-Speaker/Audio-Text/audio/snippet_1.wav",
        "/home/qin/ZHTLLM/3D-Speaker/Audio-Text/audio/snippet_2.wav",
        "/home/qin/ZHTLLM/3D-Speaker/Audio-Text/audio/snippet_3.wav",
    ]

    # Define the root of the GraphRAG project workspace
    project_root = Path(__file__).resolve().parent
    
    # Define the root directory for all GraphRAG operations (input, output, etc.)
    graphrag_working_dir = str(project_root / "ragtest")

    print(f"Dialogue file: {DIALOGUE_AUDIO_PATH}")
    print(f"Speaker samples: {SPEAKER_SAMPLE_PATHS}")
    print(f"GraphRAG working directory: {graphrag_working_dir}")
    print("-" * 20)
    
    # The pipeline function now handles file existence checks internally
    # Note: Running directly will fail if the calling context isn't async.
    # This __main__ block is for demonstration and might need asyncio.run().
    asyncio.run(run_online_pipeline(
        rag_root=graphrag_working_dir,
        dialogue_audio_path=DIALOGUE_AUDIO_PATH,
        speaker_samples={
            "张三": "/home/qin/ZHTLLM/3D-Speaker/Audio-Text/audio/snippet_1.wav",
            "李四": "/home/qin/ZHTLLM/3D-Speaker/Audio-Text/audio/snippet_2.wav",
            "王五": "/home/qin/ZHTLLM/3D-Speaker/Audio-Text/audio/snippet_3.wav",
        },
    ))
    
    print("\n--- ZHTLLM Online Pipeline Finished ---")

