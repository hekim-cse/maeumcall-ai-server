"""Download the configured, pinned NLU model into an external Hugging Face cache."""

from huggingface_hub import snapshot_download

from core.config import HF_MODEL_NAME, HF_MODEL_REVISION


def main() -> None:
    snapshot = snapshot_download(repo_id=HF_MODEL_NAME, revision=HF_MODEL_REVISION)
    print(snapshot)


if __name__ == "__main__":
    main()
