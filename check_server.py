#!/usr/bin/env python3
"""
Simple server status checker
"""

import requests
import sys

def check_server():
    try:
        response = requests.get("http://localhost:8000", timeout=5)
        print(f"✅ Server is running! Status: {response.status_code}")
        return True
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running or not accessible")
        print("💡 To start the server, run: python main.py")
        return False
    except Exception as e:
        print(f"❌ Error checking server: {e}")
        return False

if __name__ == "__main__":
    check_server()
