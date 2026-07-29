# DA-19 🟡 BaseClient Thread Lock Serializes Concurrent Requests

**Component:** `vinu-simulator`
**Files Changed:** *(pending)*

## Problem

`BaseClient` wraps all HTTP requests with `threading.Lock()`. This serializes every call to the same client.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
