from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_cloudrun_build_context_keeps_required_sources() -> None:
    dockerignore = {
        line.strip()
        for line in (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "frontend" not in dockerignore
    assert "src" not in dockerignore
    assert "configs" not in dockerignore
    assert "artifacts/runtime/models" not in dockerignore
    assert "artifacts/phase2" not in dockerignore
    assert "frontend/node_modules" in dockerignore


def test_cloudrun_container_has_same_origin_and_bounded_runtime_contract() -> None:
    dockerfile = (PROJECT_ROOT / "deploy/cloudrun/Dockerfile").read_text(
        encoding="utf-8"
    )
    nginx = (PROJECT_ROOT / "deploy/cloudrun/nginx.conf.template").read_text(
        encoding="utf-8"
    )
    deploy = (PROJECT_ROOT / "deploy/cloudrun/Deploy-ResistSenseCloudRun.ps1").read_text(
        encoding="utf-8"
    )
    assert 'ARG NEXT_PUBLIC_API_URL=""' in dockerfile
    assert "location /api/" in nginx
    assert "location = /health" in nginx
    assert "--concurrency 1" in deploy
    assert "--min-instances 0" in deploy
    assert "--max-instances 1" in deploy
    assert "--set-secrets" in deploy
    assert "OPENAI_API_KEY" in deploy
