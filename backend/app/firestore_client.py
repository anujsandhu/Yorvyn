"""
Firebase Firestore client initialization and connection management.

This module provides a reusable Firestore client configured via environment variables.
"""

import os
from typing import Optional
import firebase_admin
from firebase_admin import credentials, firestore


# Singleton instance
_db_instance: Optional[firestore.client.Client] = None


def initialize_firebase() -> None:
    """
    Initialize Firebase Admin SDK using service account JSON.
    
    Reads FIREBASE_SERVICE_ACCOUNT_PATH from environment.
    Must be called once at app startup.
    
    Raises:
        FileNotFoundError: If service account JSON not found
        ValueError: If Firebase already initialized
    """
    global _db_instance
    
    if firebase_admin._apps:
        print("Firebase already initialized, skipping...")
        return
    
    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
    if not service_account_path:
        raise ValueError(
            "FIREBASE_SERVICE_ACCOUNT_PATH environment variable not set. "
            "Download your Firebase service account JSON and set the path."
        )
    
    if not os.path.exists(service_account_path):
        raise FileNotFoundError(f"Service account JSON not found at {service_account_path}")
    
    cred = credentials.Certificate(service_account_path)
    firebase_admin.initialize_app(cred)
    _db_instance = firestore.client()
    print(f"✓ Firebase initialized from {service_account_path}")


def get_db() -> firestore.client.Client:
    """
    Get the Firestore client instance.
    
    Returns:
        Initialized Firestore client
        
    Raises:
        RuntimeError: If Firebase not initialized
    """
    global _db_instance
    
    if _db_instance is None:
        raise RuntimeError(
            "Firestore client not initialized. "
            "Call initialize_firebase() at app startup."
        )
    
    return _db_instance


def close_firebase() -> None:
    """Close Firebase connection."""
    global _db_instance
    if _db_instance:
        firebase_admin.delete_app(firebase_admin.get_app())
        _db_instance = None
