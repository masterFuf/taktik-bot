"""What the Lab shows of an avatar crop, on every platform: whether it was made and its size.

Never the image: a `data:image/jpeg;base64,...` runs to tens of kilobytes and the Lab's stdout
carries paths and short results only.
"""

from typing import Any, Dict, Optional


def avatar_result(data_url: Optional[str]) -> Dict[str, Any]:
    """The result of an action that crops an avatar, from the production crop's answer."""
    size_kb = len(data_url) * 3 // 4 // 1024 if data_url else 0
    return {"success": bool(data_url),
            "message": f"avatar cropped ({size_kb} KB)" if data_url else "avatar not found on screen",
            "details": {"extracted": bool(data_url), "size_kb": size_kb}}
