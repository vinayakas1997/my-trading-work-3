import json

from vinu_agent.tools.angle_consensus_tool import CompareAnglesTool


def _tool() -> CompareAnglesTool:
    return CompareAnglesTool()


class TestCompareAnglesTool:
    def test_directional_agreement(self) -> None:
        result = json.loads(_tool().execute(
            comparison_type="directional",
            angle_a_name="arima", angle_a_row_count=100, angle_a_value=0.02,
            angle_b_name="chronos", angle_b_row_count=80, angle_b_value=0.05,
        ))
        assert result["status"] == "ok"
        assert result["outcome"] == "agree"
        assert "0.02" in result["reasoning"]

    def test_directional_divergence(self) -> None:
        result = json.loads(_tool().execute(
            comparison_type="directional",
            angle_a_name="arima", angle_a_row_count=100, angle_a_value=0.02,
            angle_b_name="chronos", angle_b_row_count=80, angle_b_value=-0.01,
        ))
        assert result["outcome"] == "diverge"

    def test_insufficient_data(self) -> None:
        result = json.loads(_tool().execute(
            comparison_type="directional",
            angle_a_name="arima", angle_a_row_count=0, angle_a_value=0.02,
            angle_b_name="chronos", angle_b_row_count=80, angle_b_value=0.05,
        ))
        assert result["outcome"] == "insufficient_data"

    def test_magnitude_with_custom_tolerance(self) -> None:
        result = json.loads(_tool().execute(
            comparison_type="magnitude",
            angle_a_name="arima", angle_a_row_count=100, angle_a_value=0.02,
            angle_b_name="chronos", angle_b_row_count=80, angle_b_value=0.03,
            tolerance=0.05,
        ))
        assert result["outcome"] == "diverge"  # ~33% relative distance > 5% tolerance

    def test_categorical_uses_real_shipped_adjacency_config(self) -> None:
        result = json.loads(_tool().execute(
            comparison_type="categorical",
            angle_a_name="regime_analysis", angle_a_row_count=50, angle_a_value="bull",
            angle_b_name="trend_lifecycle", angle_b_row_count=50, angle_b_value="uptrend",
        ))
        assert result["outcome"] == "agree"

    def test_unknown_comparison_type_errors(self) -> None:
        result = json.loads(_tool().execute(
            comparison_type="not_a_real_type",
            angle_a_name="a", angle_a_row_count=1, angle_a_value=1,
            angle_b_name="b", angle_b_row_count=1, angle_b_value=1,
        ))
        assert result["status"] == "error"
