"""POST /api/v1/prompt/enhance — 提示词增强。

使用 Gemma 模型对用户提示词进行自动润色和扩展，
提高生成视频的质量和细节。
"""

from fastapi import APIRouter, HTTPException

from jiandou.api.schemas import PromptEnhanceRequest

router = APIRouter(prefix="/api/v1", tags=["Prompt"])


# Prompt enhancement templates when Gemma is not available
ENHANCE_TEMPLATES = {
    "cinematic": "Cinematic shot, professional lighting, {prompt}, high quality, detailed",
    "anime": "Anime style, Studio Ghibli inspired, {prompt}, vibrant colors, hand-drawn",
    "realistic": "Photorealistic, 8K, {prompt}, natural lighting, sharp focus",
    "artistic": "Artistic rendering, {prompt}, beautiful composition, award-winning",
    "fantasy": "Fantasy scene, magical atmosphere, {prompt}, ethereal lighting, epic scale",
}


def _resolve_gemma_path() -> str:
    try:
        from jiandou.storage.config import load_config
        config = load_config()
        registry = config.models.registries
        # Check for gemma in registry
        return ""
    except Exception:
        return ""


@router.post("/prompt/enhance")
async def enhance_prompt(req: PromptEnhanceRequest):
    """使用 AI 增强提示词。

    当 Gemma 模型不可用时，使用模板增强。
    """
    style = req.style if req.style in ENHANCE_TEMPLATES else "cinematic"
    template = ENHANCE_TEMPLATES.get(style, ENHANCE_TEMPLATES["cinematic"])

    # Try Gemma-based enhancement if available
    enhanced = None
    gemma_path = _resolve_gemma_path()

    if gemma_path:
        try:
            enhanced = _enhance_with_gemma(req.prompt, style, gemma_path)
        except Exception:
            pass

    if not enhanced:
        enhanced = template.format(prompt=req.prompt)

    return {
        "original": req.prompt,
        "enhanced": enhanced,
        "style": style,
        "method": "gemma" if gemma_path else "template",
    }


def _enhance_with_gemma(prompt: str, style: str, model_path: str) -> str:
    """使用 Gemma 模型增强提示词。

    Not yet implemented — requires Gemma model to be loaded.
    """
    # TODO: Load Gemma model and run inference
    # For now, raise to fallback to template
    raise NotImplementedError("Gemma enhancement not yet available")
