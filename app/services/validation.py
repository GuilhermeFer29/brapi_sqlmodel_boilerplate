from typing import Any
def try_validate(model_path: str, payload: Any):
    try:
        module_path, class_name = model_path.split(":")
        mod = __import__(module_path, fromlist=[class_name])
        cls = getattr(mod, class_name)
    except Exception:
        return False, None, "model-not-found"
    try:
        obj = cls.model_validate(payload)  # pydantic v2
        return True, obj, None
    except Exception as e:
        return False, None, str(e)
