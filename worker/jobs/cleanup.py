def cleanup_media(r2_key: str):
    # Hook for R2 deletion later—non-fatal for MVP
    return {"deleted": False, "reason": "not_implemented"}