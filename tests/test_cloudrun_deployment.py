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
    assert "--startup-probe" in deploy
    assert "--set-secrets" in deploy
    assert "OPENAI_API_KEY" in deploy
    assert "RESISTSENSE_USAGE_COUNTER_ENABLED=true" in deploy
    start = (PROJECT_ROOT / "deploy/cloudrun/start.sh").read_text(encoding="utf-8")
    assert 'curl --fail --silent "http://127.0.0.1:8000/health"' in start
    assert 'curl --fail --silent "http://127.0.0.1:3000/"' in start
    assert start.index("npm run start") < start.index("nginx -c")


def test_operations_script_scopes_budget_and_shutdown_to_resistsense() -> None:
    operations = (
        PROJECT_ROOT / "deploy/cloudrun/Configure-ResistSenseOperations.ps1"
    ).read_text(encoding="utf-8")
    guard = (PROJECT_ROOT / "deploy/budget_guard/main.py").read_text(
        encoding="utf-8"
    )
    restore = (
        PROJECT_ROOT / "deploy/cloudrun/Restore-ResistSensePublicAccess.ps1"
    ).read_text(encoding="utf-8")
    assert '[decimal]$BudgetAmount = 34' in operations
    assert '[string]$BudgetCurrency = "PEN"' in operations
    assert '[string]$AlertEmail = "arkhangio@gmail.com"' in operations
    assert '"percent=0.50,basis=current-spend"' in operations
    assert '"percent=1.00,basis=current-spend"' in operations
    assert "--filter-projects $projectFilter" in operations
    assert "RESISTSENSE_USAGE_COUNTER_ENABLED=true" in operations
    assert "roles/datastore.user" in operations
    assert "roles/run.admin" in operations
    assert "roles/iam.serviceAccountUser" in operations
    assert (
        "iam service-accounts add-iam-policy-binding $runtimeServiceAccount"
        in operations
    )
    assert "billing projects unlink" not in operations
    assert "billing projects unlink" not in guard
    assert "remove_public_invoker" in guard
    assert "INGRESS_TRAFFIC_INTERNAL_ONLY" in guard
    assert "updateMask=ingress" in guard
    assert '"allUsers"' in restore
    assert '"roles/run.invoker"' in restore
    assert '--ingress "all"' in restore
