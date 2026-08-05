from vinu_infra.llm.providers import ProviderCapabilities


def test_empty_pricing():
    caps = ProviderCapabilities(name="test")
    p = caps.get_model_pricing("gpt-4")
    assert p == {"input_per_1m": 0.0, "output_per_1m": 0.0}


def test_pricing_by_model():
    caps = ProviderCapabilities(
        name="test",
        pricing={
            "gpt-4": {"input_per_1m": 30.0, "output_per_1m": 60.0},
        },
    )
    p = caps.get_model_pricing("gpt-4")
    assert p["input_per_1m"] == 30.0
    assert p["output_per_1m"] == 60.0


def test_pricing_fallback_to_default():
    caps = ProviderCapabilities(
        name="test",
        pricing={
            "default": {"input_per_1m": 1.0, "output_per_1m": 2.0},
            "gpt-4": {"input_per_1m": 30.0, "output_per_1m": 60.0},
        },
    )
    p = caps.get_model_pricing("unknown-model")
    assert p["input_per_1m"] == 1.0
    assert p["output_per_1m"] == 2.0


def test_estimate_cost():
    caps = ProviderCapabilities(
        name="test",
        pricing={
            "gpt-4": {"input_per_1m": 30.0, "output_per_1m": 60.0},
        },
    )
    cost = caps.estimate_cost("gpt-4", prompt_tokens=1000, completion_tokens=500)
    expected = (1000 / 1_000_000) * 30.0 + (500 / 1_000_000) * 60.0
    assert cost == round(expected, 6)


def test_estimate_cost_zero_tokens():
    caps = ProviderCapabilities(name="test", pricing={
        "gpt-4": {"input_per_1m": 30.0, "output_per_1m": 60.0},
    })
    cost = caps.estimate_cost("gpt-4", 0, 0)
    assert cost == 0.0


def test_estimate_cost_no_pricing():
    caps = ProviderCapabilities(name="test")
    cost = caps.estimate_cost("gpt-4", 1000, 500)
    assert cost == 0.0
