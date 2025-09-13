"""
Authentication and utility functions for What2Wear backend
"""
import os
import requests
from fastapi import Header, HTTPException
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"] 
BUCKET = os.environ.get("STORAGE_BUCKET", "wardrobe")


def get_user_id(authorization: str = Header(..., description="Bearer token")) -> str:
    """
    Extract and validate user ID from Supabase JWT token
    """
    print(f"DEBUG: Received authorization header: {authorization[:50]}...")
    
    if not authorization.startswith("Bearer "):
        print("DEBUG: Missing bearer token prefix")
        raise HTTPException(status_code=401, detail="Missing bearer token")
    
    token = authorization.split(" ", 1)[1]
    print(f"DEBUG: Extracted token: {token[:50]}...")
    
    try:
        auth_url = f"{SUPABASE_URL}/auth/v1/user"
        print(f"DEBUG: Making request to: {auth_url}")
        
        response = requests.get(
            auth_url,
            headers={"Authorization": f"Bearer {token}", "apikey": SUPABASE_ANON_KEY},
            timeout=5
        )
        
        print(f"DEBUG: Auth response status: {response.status_code}")
        print(f"DEBUG: Auth response: {response.text[:200]}...")
        
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail=f"Invalid token: {response.text}")
            
        user_data = response.json()
        print(f"DEBUG: User data: {user_data}")
        return user_data["id"]
        
    except requests.RequestException as e:
        print(f"DEBUG: Request exception: {e}")
        raise HTTPException(status_code=401, detail="Token validation failed")


def get_user_supabase_client(authorization: str = Header(..., description="Bearer token")) -> Client:
    """
    Create an authenticated Supabase client for the current user
    This client will respect RLS policies for the authenticated user
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    
    token = authorization.split(" ", 1)[1]
    
    # Create client with anon key and custom headers for user auth
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    
    # Override the auth token for this client instance
    client.options.headers.update({"Authorization": f"Bearer {token}"})
    
    return client


def create_signed_url(object_path: str, seconds: int = 120) -> str:
    """
    Create a short-lived signed URL for a Supabase Storage object
    
    Args:
        object_path: Full path like "wardrobe/{user_id}/{uuid}.webp"
        seconds: Expiry time in seconds
        
    Returns:
        Full signed URL
    """
    # Remove bucket prefix if present
    if object_path.startswith(f"{BUCKET}/"):
        object_path = object_path[len(BUCKET)+1:]
    
    url = f"{SUPABASE_URL}/storage/v1/object/sign/{BUCKET}/{object_path}"
    headers = {
        "Authorization": f"Bearer {SERVICE_KEY}",
        "apikey": SERVICE_KEY,
        "Content-Type": "application/json"
    }
    payload = {"expiresIn": seconds}
    
    try:
        print(f"DEBUG: Creating signed URL for: {object_path}")
        print(f"DEBUG: Request URL: {url}")
        
        response = requests.post(url, headers=headers, json=payload, timeout=5)
        
        print(f"DEBUG: Signed URL response status: {response.status_code}")
        print(f"DEBUG: Signed URL response: {response.text}")
        
        if response.status_code != 200:
            print(f"ERROR: Failed to create signed URL. Status: {response.status_code}, Response: {response.text}")
            raise HTTPException(status_code=500, detail=f"Cannot create signed storage URL: {response.text}")
            
        signed_data = response.json()
        full_url = f"{SUPABASE_URL}/storage/v1/{signed_data['signedURL']}"
        print(f"DEBUG: Generated signed URL: {full_url}")
        return full_url
        
    except requests.RequestException as e:
        print(f"ERROR: Storage service request failed: {e}")
        raise HTTPException(status_code=500, detail=f"Storage service unavailable: {str(e)}")
