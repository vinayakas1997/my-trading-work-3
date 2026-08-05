"""Vendored Kronos model package (github.com/shiyu-coder/Kronos, MIT License).

See module.py / kronos.py for the vendored source and attribution. Exposes the
same public API as the upstream `model` package: Kronos, KronosTokenizer,
KronosPredictor, plus get_model_class for parity.
"""

from .kronos import KronosTokenizer, Kronos, KronosPredictor

model_dict = {
    'kronos_tokenizer': KronosTokenizer,
    'kronos': Kronos,
    'kronos_predictor': KronosPredictor
}


def get_model_class(model_name):
    if model_name in model_dict:
        return model_dict[model_name]
    else:
        print(f"Model {model_name} not found in model_dict")
        raise NotImplementedError
