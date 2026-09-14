"""Register and checksum original source PDFs for the evaluator."""

from src.evaluation_agent.runner import EvaluationRunner


def main() -> None:
    documents = EvaluationRunner().register_documents()
    for document in documents:
        print(
            f"{document.spec.slug}: {document.page_count} halaman, "
            f"sha256={document.checksum_sha256}"
        )


if __name__ == "__main__":
    main()
