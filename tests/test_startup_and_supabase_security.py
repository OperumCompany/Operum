from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_startup_script_uses_project_venv_and_waits_for_vite_root():
    script = (ROOT_DIR / "iniciar.ps1").read_text(encoding="utf-8")

    assert '$projectPython = Join-Path $projectDir ".venv\\Scripts\\python.exe"' in script
    assert "-FilePath $projectPython" in script
    assert 'http://127.0.0.1:5173/' in script
    assert "-MaxRetries 90" in script
    assert '"--clear"' in script


def test_supabase_security_migration_protects_all_alerted_tables():
    migration_path = ROOT_DIR / "scripts" / "secure_supabase_rls.py"
    spec = spec_from_file_location("secure_supabase_rls", migration_path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    assert set(module.SECURITY_TABLES) == {
        "portfolio_transactions",
        "model_versions",
        "asset_analysis_snapshots",
        "analysis_jobs",
        "prediction_outcomes",
    }
    assert "enable row level security" in module.SECURITY_SQL.lower()
    assert "revoke all privileges" in module.SECURITY_SQL.lower()
