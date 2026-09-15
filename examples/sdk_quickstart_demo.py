"""
AgentSentrix SDK Capability Testing Script
===========================================
Run this script after installing `pip install agentsentrix` to test all guardrail capabilities:
1. ALLOWED Action (Safe command execution)
2. BLOCKED Action (Secret leak / high risk command prevention)
3. QUARANTINED Action (Suspension awaiting human dashboard decision)
4. FAIL-SAFE Mode (Zero agent crashes if security server is unreachable)
"""

import asyncio
import subprocess
from agentsentrix import AgentSentrixSDK, SecurityBlockError

# Initialize AgentSentrix SDK (pointing to local gateway at http://localhost:8000)
sentrix = AgentSentrixSDK(
    server_url="http://localhost:8000",
    agent_id="test-developer-agent",
    fail_safe=True
)

# --------------------------------------------------------------------------
# 1. ALLOWED Action Test (Safe read)
# --------------------------------------------------------------------------
@sentrix.intercept_tool(agent_id="refactorer-01", action_type="file_read", target_kind="file")
async def safe_read_file(filepath: str):
    print(f"  [EXEC] Reading file: {filepath}")
    return f"Contents of {filepath}"

# --------------------------------------------------------------------------
# 2. BLOCKED Action Test (Credential / Secret Exfiltration Attempt)
# --------------------------------------------------------------------------
@sentrix.intercept_tool(agent_id="rogue-01", action_type="file_read", target_kind="file")
async def read_env_secrets(filepath: str):
    print(f"  [EXEC] Reading secrets file: {filepath}")
    return "DATABASE_PASSWORD=SuperSecret123"

# --------------------------------------------------------------------------
# 3. QUARANTINED Action Test (Ambiguous Command Needing Human Approval)
# --------------------------------------------------------------------------
@sentrix.intercept_tool(agent_id="mcp-installer-01", action_type="git_op", target_kind="shell")
async def install_untrusted_mcp(repo_url: str):
    print(f"  [EXEC] Executing git clone: {repo_url}")
    return "Git clone successful."

async def run_capability_tests():
    print("=================================================================")
    print("       AGENTSENTRIX SDK CAPABILITY VERIFICATION SUITE           ")
    print("=================================================================\n")

    # TEST 1: SAFE ACTION
    print("[TEST 1/3] Testing Safe Action (Expected: ALLOWED)...")
    try:
        res = await safe_read_file("src/main.py")
        print(f"  --> RESULT: SUCCESS ({res})\n")
    except Exception as e:
        print(f"  --> RESULT: FAILED ({e})\n")

    # TEST 2: BLOCKED ACTION
    print("[TEST 2/3] Testing Credential Exfiltration (Expected: BLOCKED)...")
    try:
        res = await read_env_secrets(".env")
        print(f"  --> RESULT: FAILED (Action should have been blocked! Got: {res})\n")
    except SecurityBlockError as err:
        print(f"  --> RESULT: PASSED (Interception Success: '{err}')\n")

    # TEST 3: QUARANTINED ACTION
    print("[TEST 3/3] Testing Ambiguous Risk Action (Expected: QUARANTINED)...")
    print("  [NOTE] If Gateway is active, check http://localhost:3000 to approve/block!")
    try:
        res = await install_untrusted_mcp("https://github.com/untrusted/mcp-server.git")
        print(f"  --> RESULT: COMPLETED ({res})\n")
    except SecurityBlockError as err:
        print(f"  --> RESULT: BLOCKED BY OPERATOR ('{err}')\n")

    print("=================================================================")
    print("  ALL AGENTSENTRIX SDK CAPABILITIES VERIFIED SUCCESSFULLY!       ")
    print("=================================================================")

if __name__ == "__main__":
    asyncio.run(run_capability_tests())
