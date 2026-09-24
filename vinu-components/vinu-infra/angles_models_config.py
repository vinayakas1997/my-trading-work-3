"""Single source of truth for which model-category angles actually load a
pretrained checkpoint, what their default is, and where it comes from.
Follow-up to Decision 4 of missing-pieces-of-system/new-theory-of-
trading/01-planning.md (per-angle model-selection policy) -- that
decision only got `chronos` fully wired through
`vinu_infra.model_policy.get_model_checkpoint()`; this file is the
groundwork for wiring the rest, and the honest record of which ones
can't be wired at all because they don't have a checkpoint in the first
place.

A `.py` file rather than `.json` on purpose: config-as-data needs
comments to stay honest about WHY a default was chosen (see each entry's
`notes`), and JSON can't carry that -- the comment would either live
nowhere or rot in a separate doc nobody updates alongside the value.

**Real finding, checked against every one of the 11 `category: model`
angles' actual compute.py before writing this** (not assumed from
names): only 4 of them load a real pretrained checkpoint at all.
- chronos, timesfm, timer_timerxl, kronos: genuine foundation models,
  weights downloaded via `vinu_infra.models.ensure_model` and cached.
- dlinear, itransformer, lstm, patchtst, tft, lpatchtst,
  tips_regime_aware_transformer: each defines and trains its own small
  model FRESH on every call (e.g. dlinear's `compute.py` defines a
  `DLinear(nn.Module)` class inline and fits it per invocation). There
  is no pretrained checkpoint for these at all -- listing a fake
  "checkpoint" entry for them here would imply a config knob that
  doesn't exist and can't do anything if set.

Usage (once an angle is wired the way chronos already is):
    from vinu_infra.angles_models_config import ANGLE_MODEL_CONFIG
    from vinu_infra.model_policy import get_model_checkpoint

    cfg = ANGLE_MODEL_CONFIG["chronos"]
    _MODEL_REGISTRY_NAME = get_model_checkpoint(ANGLE_NAME, cfg.default_registry_name)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AngleModelConfig:
    angle_name: str
    # The key into vinu_infra/models.py's MODELS dict -- NOT a raw HF
    # repo id. get_model_checkpoint()'s override also names a registry
    # key (see chronos's own compute.py comment on this), so any swap
    # can only select an already-registered, already-vetted checkpoint.
    default_registry_name: str
    # The actual HF repo id the default registry name resolves to today
    # -- kept here too, redundantly, purely so this file is readable on
    # its own without also opening models.py to know what "chronos-t5-
    # large" means.
    default_hf_repo_id: str
    source: str  # always "huggingface" today; a field, not a hardcode,
                 # in case a future model source (a private registry, a
                 # local-only checkpoint) needs a different resolution path.
    override_env_var: str  # VINU_<ANGLE>_CHECKPOINT, spelled out here
                            # rather than computed, so grepping the env
                            # var name finds this file even if the naming
                            # convention in model_policy.py ever changes.
    notes: str


# Angles with a genuine pretrained checkpoint. All four already have
# real, working code (`ensure_model` calls); only `chronos` is actually
# wired through `get_model_checkpoint()` yet (Decision 4) -- wiring
# `timesfm`/`timer_timerxl`/`kronos` the same way is the concrete
# follow-up task this file exists to make easy, not automatic.
ANGLE_MODEL_CONFIG: dict[str, AngleModelConfig] = {
    "chronos": AngleModelConfig(
        angle_name="chronos",
        default_registry_name="chronos-t5-large",
        default_hf_repo_id="amazon/chronos-t5-large",
        source="huggingface",
        override_env_var="VINU_CHRONOS_CHECKPOINT",
        notes=(
            "Already fully wired (Decision 4) -- compute.py resolves "
            "CHECKPOINT via get_model_checkpoint() against this same "
            "registry. chronos-t5-tiny (8M params) is also registered "
            "for a faster/cheaper override; chronos-t5-large (710M) is "
            "the decided default for forecast quality over speed."
        ),
    ),
    "timesfm": AngleModelConfig(
        angle_name="timesfm",
        default_registry_name="timesfm-2.5-200m-pytorch",
        default_hf_repo_id="google/timesfm-2.5-200m-pytorch",
        source="huggingface",
        override_env_var="VINU_TIMESFM_CHECKPOINT",
        notes=(
            "NOT yet wired through get_model_checkpoint() -- compute.py "
            "still has CHECKPOINT hardcoded as a plain string constant. "
            "Wiring this is a copy of exactly what chronos/compute.py "
            "already does."
        ),
    ),
    "timer_timerxl": AngleModelConfig(
        angle_name="timer_timerxl",
        default_registry_name="timer-timerxl",
        default_hf_repo_id="thuml/timer-base-84m",
        source="huggingface",
        override_env_var="VINU_TIMER_TIMERXL_CHECKPOINT",
        notes=(
            "NOT yet wired -- compute.py calls "
            "ensure_model('timer-timerxl') with the registry name "
            "hardcoded directly in the call, not read from a settable "
            "constant. Wiring this needs a small refactor (introduce a "
            "_MODEL_REGISTRY_NAME constant first, the same shape chronos "
            "has) before get_model_checkpoint() has anywhere to plug in."
        ),
    ),
    "kronos": AngleModelConfig(
        angle_name="kronos",
        default_registry_name="kronos",
        default_hf_repo_id="NeoQuasar/Kronos-base",
        source="huggingface",
        override_env_var="VINU_KRONOS_CHECKPOINT",
        notes=(
            "NOT yet wired -- same pattern as timer_timerxl "
            "(ensure_model('kronos') called directly). Also loads a "
            "SECOND, separate registry entry for its tokenizer "
            "('kronos-tokenizer' -> NeoQuasar/Kronos-Tokenizer-base) that "
            "isn't represented as its own AngleModelConfig entry here -- "
            "the tokenizer isn't independently swappable the way the "
            "base model checkpoint is, so it's out of scope for this "
            "per-angle override mechanism, not an oversight."
        ),
    ),
}

# Angles tagged category: model that do NOT have a pretrained checkpoint
# at all -- each trains its own small architecture fresh on every call.
# Listed explicitly (not just left out of ANGLE_MODEL_CONFIG silently)
# so a future reader checking "why isn't X in the config" gets a real
# answer here instead of having to go re-derive it from compute.py again.
NO_CHECKPOINT_MODEL_ANGLES: frozenset[str] = frozenset({
    "dlinear", "itransformer", "lstm", "patchtst", "tft", "lpatchtst",
    "tips_regime_aware_transformer",
})
