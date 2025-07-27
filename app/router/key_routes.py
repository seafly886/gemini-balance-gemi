from fastapi import APIRouter, Depends, Request, HTTPException
from app.service.key.key_manager import KeyManager, get_key_manager_instance
from app.core.security import verify_auth_token
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class KeyUsageModeRequest(BaseModel):
    mode: str  # "polling" or "fixed"
    threshold: Optional[int] = None

@router.get("/api/keys")
async def get_keys_paginated(
    request: Request,
    page: int = 1,
    limit: int = 10,
    search: str = None,
    fail_count_threshold: int = None,
    status: str = "all",  # 'valid', 'invalid', 'all'
    key_manager: KeyManager = Depends(get_key_manager_instance),
):
    """
    Get paginated, filtered, and searched keys.
    """
    auth_token = request.cookies.get("auth_token")
    if not auth_token or not verify_auth_token(auth_token):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    all_keys_with_status = await key_manager.get_keys_by_status()

    # Filter by status
    if status == "valid":
        keys_to_filter = all_keys_with_status["valid_keys"]
    elif status == "invalid":
        keys_to_filter = all_keys_with_status["invalid_keys"]
    else:
        # Combine both for 'all' status, which might be useful for a unified view if ever needed
        keys_to_filter = {**all_keys_with_status["valid_keys"], **all_keys_with_status["invalid_keys"]}

    # Further filtering (search and fail_count_threshold)
    filtered_keys = {}
    for key, key_info in keys_to_filter.items():
        # Handle both old format (int) and new format (dict)
        if isinstance(key_info, dict):
            fail_count = key_info.get("fail_count", 0)
            usage_count = key_info.get("usage_count", 0)
        else:
            fail_count = key_info
            usage_count = 0

        search_match = True
        if search:
            search_match = search.lower() in key.lower()

        fail_count_match = True
        if fail_count_threshold is not None:
            fail_count_match = fail_count >= fail_count_threshold

        if search_match and fail_count_match:
            filtered_keys[key] = {"fail_count": fail_count, "usage_count": usage_count}

    # Pagination
    keys_list = list(filtered_keys.items())
    total_items = len(keys_list)
    start_index = (page - 1) * limit
    end_index = start_index + limit
    paginated_keys = dict(keys_list[start_index:end_index])

    return {
        "keys": paginated_keys,
        "total_items": total_items,
        "total_pages": (total_items + limit - 1) // limit,
        "current_page": page,
    }

@router.get("/api/keys/all")
async def get_all_keys(
    request: Request,
    key_manager: KeyManager = Depends(get_key_manager_instance),
):
    """
    Get all keys (both valid and invalid) for bulk operations.
    """
    auth_token = request.cookies.get("auth_token")
    if not auth_token or not verify_auth_token(auth_token):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    all_keys_with_status = await key_manager.get_keys_by_status()

    return {
        "valid_keys": list(all_keys_with_status["valid_keys"].keys()),
        "invalid_keys": list(all_keys_with_status["invalid_keys"].keys()),
        "total_count": len(all_keys_with_status["valid_keys"]) + len(all_keys_with_status["invalid_keys"])
    }

@router.get("/api/keys/usage-mode")
async def get_key_usage_mode(
    request: Request,
    key_manager: KeyManager = Depends(get_key_manager_instance),
):
    """
    Get current key usage mode and status.
    """
    auth_token = request.cookies.get("auth_token")
    if not auth_token or not verify_auth_token(auth_token):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    try:
        status = await key_manager.get_usage_mode_status()
        return JSONResponse(content=status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get usage mode status: {str(e)}")

@router.post("/api/keys/usage-mode")
async def set_key_usage_mode(
    request: Request,
    key_manager: KeyManager = Depends(get_key_manager_instance),
):
    """
    Set key usage mode (polling or fixed) and optionally update threshold.
    """
    auth_token = request.cookies.get("auth_token")
    if not auth_token or not verify_auth_token(auth_token):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    try:
        # Parse JSON data from request body
        try:
            request_body = await request.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail="Invalid JSON in request body")

        # Validate mode
        mode = request_body.get("mode")
        if not mode or mode not in ["polling", "fixed"]:
            raise HTTPException(status_code=400, detail="Mode must be 'polling' or 'fixed'")

        # Set usage mode
        success = await key_manager.set_usage_mode(mode)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to set usage mode")

        # Set threshold if provided
        threshold = request_body.get("threshold")
        if threshold is not None:
            if threshold < 1:
                raise HTTPException(status_code=400, detail="Threshold must be at least 1")

            threshold_success = await key_manager.set_usage_threshold(threshold)
            if not threshold_success:
                raise HTTPException(status_code=400, detail="Failed to set usage threshold")

        # Return updated status
        status = await key_manager.get_usage_mode_status()
        return JSONResponse(content={
            "success": True,
            "message": f"Key usage mode set to {mode}",
            "status": status
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set usage mode: {str(e)}")

@router.post("/api/keys/reset-usage-counts")
async def reset_usage_counts(
    request: Request,
    key_manager: KeyManager = Depends(get_key_manager_instance),
):
    """
    Reset all key usage counts.
    """
    auth_token = request.cookies.get("auth_token")
    if not auth_token or not verify_auth_token(auth_token):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    try:
        await key_manager.reset_usage_counts()
        return JSONResponse(content={
            "success": True,
            "message": "All key usage counts have been reset"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset usage counts: {str(e)}")
