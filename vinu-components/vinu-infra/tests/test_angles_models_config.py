from __future__ import annotations

from vinu_infra.angles_models_config import (
    ANGLE_MODEL_CONFIG,
    NO_CHECKPOINT_MODEL_ANGLES,
)
from vinu_infra.models import MODELS


def test_every_entrys_registry_name_exists_in_the_real_shared_registry():
    """Catches the config drifting from vinu-infra/models.py -- a
    default_registry_name here that isn't a real key in MODELS would
    mean ensure_model() can never actually resolve it."""
    for name, cfg in ANGLE_MODEL_CONFIG.items():
        assert cfg.default_registry_name in MODELS, (
            f"{name}: registry name {cfg.default_registry_name!r} not in vinu_infra.models.MODELS"
        )


def test_every_entrys_hf_repo_id_matches_the_real_registry_value():
    """The redundant hf_repo_id field (kept for readability) must not
    silently drift from what the registry actually resolves to."""
    for name, cfg in ANGLE_MODEL_CONFIG.items():
        assert MODELS[cfg.default_registry_name] == cfg.default_hf_repo_id, (
            f"{name}: hf_repo_id {cfg.default_hf_repo_id!r} != "
            f"MODELS[{cfg.default_registry_name!r}] = {MODELS[cfg.default_registry_name]!r}"
        )


def test_override_env_var_naming_matches_get_model_checkpoint_convention():
    for name, cfg in ANGLE_MODEL_CONFIG.items():
        expected = f"VINU_{name.upper()}_CHECKPOINT"
        assert cfg.override_env_var == expected, f"{name}: {cfg.override_env_var!r} != {expected!r}"


def test_no_overlap_between_checkpoint_and_no_checkpoint_angles():
    assert set(ANGLE_MODEL_CONFIG) & NO_CHECKPOINT_MODEL_ANGLES == set()


def test_covers_all_eleven_real_model_category_angles():
    """The 11 model-category angles confirmed during Phase 1 (see
    02-implementation-status.md's angle classification) must all be
    accounted for here, one way or the other -- either a real checkpoint
    config, or an explicit no-checkpoint entry."""
    all_model_angles = {
        "chronos", "dlinear", "itransformer", "kronos", "lpatchtst",
        "lstm", "patchtst", "tft", "timer_timerxl", "timesfm",
        "tips_regime_aware_transformer",
    }
    accounted_for = set(ANGLE_MODEL_CONFIG) | NO_CHECKPOINT_MODEL_ANGLES
    assert accounted_for == all_model_angles


def test_get_model_checkpoint_honors_an_override_for_a_not_yet_wired_angle():
    """The config file's override_env_var values are real and already
    functional through get_model_checkpoint(), even before each angle's
    own compute.py is refactored to actually call it -- proving the
    follow-up wiring work is purely mechanical, not blocked on anything
    in model_policy.py itself."""
    import importlib
    import os

    from vinu_infra import model_policy as model_policy_module

    os.environ["VINU_TIMESFM_CHECKPOINT"] = "some-override"
    try:
        importlib.reload(model_policy_module)
        cfg = ANGLE_MODEL_CONFIG["timesfm"]
        result = model_policy_module.get_model_checkpoint("timesfm", cfg.default_registry_name)
        assert result == "some-override"
    finally:
        del os.environ["VINU_TIMESFM_CHECKPOINT"]
        importlib.reload(model_policy_module)
