from resistsense.config import load_config


def test_project_configuration_loads() -> None:
    load_config.cache_clear()
    config = load_config("configs/resistsense.yaml")
    assert config.project.name == "ResistSense"
    assert config.scope.species.taxon_id == 562
    assert 3 <= len(config.scope.antibiotics) <= 5
    assert config.firewall.require_conformal_singleton is True
    assert config.modeling.antibiotics["ciprofloxacin"].strategy == "full_ensemble"
    assert all(
        policy.conformal_alpha == 0.05
        for policy in config.modeling.antibiotics.values()
    )
