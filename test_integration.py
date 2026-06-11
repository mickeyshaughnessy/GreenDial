#!/usr/bin/env python3
"""
Integration Tests for GreenDial
Tests all API endpoints through the public URL to catch deployment issues
"""
import requests
import json
import sys
import time
from datetime import datetime

# Configuration
BASE_URL = "https://greendial.org"
TEST_USER_PREFIX = f"inttest_{int(time.time())}"

# Demand-side API key (from local config.py, synced to the server by deploy.sh)
try:
    import config as _local_config
    DEMAND_API_KEY = getattr(_local_config, 'DEMAND_API_KEY', '')
except Exception:
    DEMAND_API_KEY = ''

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def log_test(name):
    print(f"\n{Colors.BLUE}▶ Testing: {name}{Colors.END}")

def log_success(message):
    print(f"  {Colors.GREEN}✓ {message}{Colors.END}")

def log_error(message):
    print(f"  {Colors.RED}✗ {message}{Colors.END}")

def log_info(message):
    print(f"  {Colors.YELLOW}ℹ {message}{Colors.END}")


class IntegrationTests:
    def __init__(self, base_url):
        self.base_url = base_url
        self.test_user = None
        self.test_user_id = None
        self.session_id = None
        self.token = None
        self.bounty_id = None
        self.suggestion_id = None
        self.activity_id = None
        self.passed = 0
        self.failed = 0
        self.errors = []

    def _headers(self):
        """Session-token header for user-scoped endpoints"""
        return {'X-Session-Token': self.token or ''}

    def _api_key_headers(self):
        """Demand-side API key header for bounty/generate endpoints"""
        return {'X-API-Key': DEMAND_API_KEY}
    
    def assert_response(self, response, expected_status=200, should_have=None, should_not_have=None):
        """Assert response properties"""
        try:
            # Check status code
            if response.status_code != expected_status:
                raise AssertionError(f"Expected status {expected_status}, got {response.status_code}")
            
            # Try to parse JSON
            try:
                data = response.json()
            except:
                if expected_status == 200:
                    raise AssertionError("Expected JSON response but got non-JSON")
                return True
            
            # Check for required fields
            if should_have:
                for field in should_have:
                    if field not in data:
                        raise AssertionError(f"Response missing required field: {field}")
            
            # Check for fields that shouldn't be there
            if should_not_have:
                for field in should_not_have:
                    if field in data:
                        raise AssertionError(f"Response has unexpected field: {field}")
            
            return True
        except AssertionError as e:
            log_error(str(e))
            log_info(f"Response: {response.text[:200]}")
            return False
    
    def test_1_ping(self):
        """Test basic API connectivity"""
        log_test("API Ping")
        try:
            response = requests.get(f"{self.base_url}/ping", timeout=10)
            if self.assert_response(response, 200, should_have=["status", "service"]):
                data = response.json()
                if data.get("status") == "ok":
                    log_success("API is responding")
                    self.passed += 1
                    return True
        except Exception as e:
            log_error(f"Connection error: {e}")
        
        self.failed += 1
        self.errors.append("API ping failed - service may be down")
        return False
    
    def test_2_stats(self):
        """Test stats endpoint (unauthenticated)"""
        log_test("Stats Endpoint")
        try:
            response = requests.get(f"{self.base_url}/stats", timeout=10)
            if self.assert_response(response, 200, should_have=["user_count"]):
                log_success("Stats endpoint working")
                self.passed += 1
                return True
        except Exception as e:
            log_error(f"Stats error: {e}")
        
        self.failed += 1
        self.errors.append("Stats endpoint failed")
        return False
    
    def test_3_signup(self):
        """Test user signup"""
        log_test("User Signup")
        username = f"{TEST_USER_PREFIX}_user"
        try:
            response = requests.post(
                f"{self.base_url}/auth",
                json={
                    "username": username,
                    "password": "test123",
                    "create_new": True,
                    "hipaa_waiver_accepted": True
                },
                timeout=10
            )
            
            if self.assert_response(response, 200, should_have=["user_id", "username", "new_user", "token"]):
                data = response.json()
                self.test_user = data
                self.test_user_id = data.get("user_id")
                self.token = data.get("token")
                if data.get("new_user") and self.test_user_id and self.token:
                    log_success(f"User created with session token: {self.test_user_id}")
                    self.passed += 1
                    return True
        except Exception as e:
            log_error(f"Signup error: {e}")
        
        self.failed += 1
        self.errors.append("User signup failed - login/signup broken")
        return False
    
    def test_4_login(self):
        """Test user login"""
        log_test("User Login")
        if not self.test_user:
            log_error("Skipped - no test user")
            return False
        
        username = self.test_user.get("username")
        try:
            response = requests.post(
                f"{self.base_url}/auth",
                json={
                    "username": username,
                    "password": "test123"
                },
                timeout=10
            )
            
            if self.assert_response(response, 200, should_have=["user_id", "username", "token"], should_not_have=["new_user"]):
                self.token = response.json().get("token")
                log_success("Login successful, token refreshed")
                self.passed += 1
                return True
        except Exception as e:
            log_error(f"Login error: {e}")
        
        self.failed += 1
        self.errors.append("User login failed")
        return False
    
    def test_5_chat(self):
        """Test chat endpoint"""
        log_test("Chat Endpoint")
        if not self.test_user_id:
            log_error("Skipped - no test user")
            return False
        
        try:
            response = requests.post(
                f"{self.base_url}/chat",
                json={
                    "user_id": self.test_user_id,
                    "text": "Hello, I need help with my health"
                },
                headers=self._headers(),
                timeout=30
            )
            
            if self.assert_response(response, 200, should_have=["response", "session_id", "user_id"]):
                data = response.json()
                self.session_id = data.get("session_id")
                response_text = data.get("response", "")
                if len(response_text) > 10:
                    log_success(f"Chat response received ({len(response_text)} chars)")
                    self.passed += 1
                    return True
        except Exception as e:
            log_error(f"Chat error: {e}")
        
        self.failed += 1
        self.errors.append("Chat endpoint failed")
        return False
    
    def test_6_profile_update(self):
        """Test profile updates through chat"""
        log_test("Profile Update via Chat")
        if not self.test_user_id:
            log_error("Skipped - no test user")
            return False
        
        try:
            response = requests.post(
                f"{self.base_url}/chat",
                json={
                    "user_id": self.test_user_id,
                    "text": "I'm 45 years old and I have diabetes. I take metformin 500mg daily."
                },
                headers=self._headers(),
                timeout=30
            )
            
            if self.assert_response(response, 200, should_have=["response"]):
                data = response.json()
                if data.get("profile_updated"):
                    profile = data.get("profile", {})
                    log_success(f"Profile updated with fields: {list(profile.keys())}")
                    self.passed += 1
                    return True
                else:
                    log_info("Profile not auto-updated (may need explicit info)")
                    self.passed += 1
                    return True
        except Exception as e:
            log_error(f"Profile update error: {e}")
        
        self.failed += 1
        self.errors.append("Profile update failed")
        return False
    
    def test_7_get_user(self):
        """Test get user endpoint"""
        log_test("Get User Profile")
        if not self.test_user_id:
            log_error("Skipped - no test user")
            return False
        
        try:
            response = requests.get(
                f"{self.base_url}/user/{self.test_user_id}",
                headers=self._headers(),
                timeout=10
            )
            
            if self.assert_response(response, 200, should_have=["user_id", "username", "profile"]):
                data = response.json()
                log_success(f"User profile retrieved")
                self.passed += 1
                return True
        except Exception as e:
            log_error(f"Get user error: {e}")
        
        self.failed += 1
        self.errors.append("Get user endpoint failed")
        return False
    
    def test_8_settings(self):
        """Test settings endpoints"""
        log_test("Settings Management")
        if not self.test_user_id:
            log_error("Skipped - no test user")
            return False
        
        try:
            # Get settings
            response = requests.get(
                f"{self.base_url}/settings/{self.test_user_id}",
                headers=self._headers(),
                timeout=10
            )

            if not self.assert_response(response, 200, should_have=["settings"]):
                raise Exception("Get settings failed")

            # Update settings
            response = requests.put(
                f"{self.base_url}/settings/{self.test_user_id}",
                json={"theme": "light"},
                headers=self._headers(),
                timeout=10
            )
            
            if self.assert_response(response, 200, should_have=["success", "settings"]):
                log_success("Settings read and updated")
                self.passed += 1
                return True
        except Exception as e:
            log_error(f"Settings error: {e}")
        
        self.failed += 1
        self.errors.append("Settings management failed")
        return False
    
    def test_9_conversations(self):
        """Test conversation history"""
        log_test("Conversation History")
        if not self.test_user_id:
            log_error("Skipped - no test user")
            return False
        
        try:
            response = requests.get(
                f"{self.base_url}/conversations/{self.test_user_id}",
                headers=self._headers(),
                timeout=10
            )
            
            if self.assert_response(response, 200, should_have=["conversations", "transcript"]):
                data = response.json()
                transcript = data.get("transcript", "")
                if len(transcript) > 0:
                    log_success(f"Conversation history retrieved ({len(transcript)} chars)")
                else:
                    log_success("Conversation endpoint working (empty history)")
                self.passed += 1
                return True
        except Exception as e:
            log_error(f"Conversation history error: {e}")
        
        self.failed += 1
        self.errors.append("Conversation history failed")
        return False
    
    def test_10_notifications(self):
        """Test notifications endpoint"""
        log_test("Notifications")
        if not self.test_user_id:
            log_error("Skipped - no test user")
            return False
        
        try:
            response = requests.get(
                f"{self.base_url}/notifications/{self.test_user_id}",
                headers=self._headers(),
                timeout=10
            )
            
            if self.assert_response(response, 200, should_have=["notifications"]):
                log_success("Notifications endpoint working")
                self.passed += 1
                return True
        except Exception as e:
            log_error(f"Notifications error: {e}")
        
        self.failed += 1
        self.errors.append("Notifications endpoint failed")
        return False
    
    def test_11_auth_enforcement(self):
        """Test that user-data reads require a session token"""
        log_test("Auth Enforcement")
        if not self.test_user_id:
            log_error("Skipped - no test user")
            return False

        try:
            # No token → 401
            r1 = requests.get(f"{self.base_url}/user/{self.test_user_id}", timeout=10)
            # Wrong token → 401
            r2 = requests.get(
                f"{self.base_url}/user/{self.test_user_id}",
                headers={'X-Session-Token': 'bogus-token'},
                timeout=10
            )
            # Bounty POST without API key → 401
            r3 = requests.post(
                f"{self.base_url}/bounty",
                json={"activity": "should be rejected"},
                timeout=10
            )
            if r1.status_code == 401 and r2.status_code == 401 and r3.status_code == 401:
                log_success("Unauthenticated reads and bounty posts correctly rejected (401)")
                self.passed += 1
                return True
            log_error(f"Expected 401s, got user={r1.status_code}, bad-token={r2.status_code}, bounty={r3.status_code}")
        except Exception as e:
            log_error(f"Auth enforcement error: {e}")

        self.failed += 1
        self.errors.append("Auth enforcement failed - endpoints are open")
        return False

    def test_12_identity_validation(self):
        """Test identity field validation"""
        log_test("Identity Validation")
        if not self.test_user_id:
            log_error("Skipped - no test user")
            return False

        try:
            # Bad email rejected
            r1 = requests.put(
                f"{self.base_url}/user/{self.test_user_id}",
                json={"email": "not-an-email"},
                headers=self._headers(), timeout=10
            )
            # Bad ETH address rejected
            r2 = requests.put(
                f"{self.base_url}/user/{self.test_user_id}",
                json={"wallets": {"eth": "0x123"}},
                headers=self._headers(), timeout=10
            )
            # Valid identity accepted
            r3 = requests.put(
                f"{self.base_url}/user/{self.test_user_id}",
                json={
                    "first_name": "Integration", "last_name": "Test",
                    "email": "inttest@example.com",
                    "wallets": {"eth": "0x" + "ab" * 20}
                },
                headers=self._headers(), timeout=10
            )
            if r1.status_code == 400 and r2.status_code == 400 and r3.status_code == 200:
                log_success("Bad email/wallet rejected; valid identity saved")
                self.passed += 1
                return True
            log_error(f"Expected 400/400/200, got {r1.status_code}/{r2.status_code}/{r3.status_code}")
        except Exception as e:
            log_error(f"Identity validation error: {e}")

        self.failed += 1
        self.errors.append("Identity validation failed")
        return False

    def test_13_bounty_flow(self):
        """Test bounty POST → suggestion generation → bounty suggestion served"""
        log_test("Bounty → Suggestion Flow")
        if not self.test_user_id:
            log_error("Skipped - no test user")
            return False
        if not DEMAND_API_KEY:
            log_info("Skipped - no DEMAND_API_KEY in local config.py")
            return False

        try:
            # Post a bounty targeting the test user
            r = requests.post(
                f"{self.base_url}/bounty",
                json={
                    "activity": "Integration test: walk 5,000 steps",
                    "health_area": "exercise",
                    "price": 0.001,
                    "currency": "ETH",
                    "user_ids": [self.test_user_id]
                },
                headers=self._api_key_headers(), timeout=10
            )
            if not self.assert_response(r, 200, should_have=["bounty_id"]):
                raise Exception("Bounty POST failed")
            self.bounty_id = r.json()["bounty_id"]

            # Force suggestion generation; bounty suggestion should be first
            r = requests.post(
                f"{self.base_url}/suggestions/{self.test_user_id}/generate",
                json={"force": True},
                headers=self._headers(), timeout=60
            )
            if not self.assert_response(r, 200, should_have=["suggestions"]):
                raise Exception("Suggestion generation failed")
            suggestions = r.json()["suggestions"]
            bounty_suggs = [s for s in suggestions if s.get("bounty_id") == self.bounty_id]
            if not bounty_suggs:
                raise Exception("Bounty suggestion not served")
            self.suggestion_id = bounty_suggs[0]["id"]
            log_success(f"Bounty served as suggestion ({len(suggestions)} total)")
            self.passed += 1
            return True
        except Exception as e:
            log_error(f"Bounty flow error: {e}")

        self.failed += 1
        self.errors.append("Bounty → suggestion flow failed")
        return False

    def test_14_activity_flow(self):
        """Test accept → activity → complete → payment_pending"""
        log_test("Accept → Complete → Payment Pending")
        if not self.suggestion_id:
            log_info("Skipped - no bounty suggestion from previous test")
            return False

        try:
            # Accept the bounty suggestion
            r = requests.post(
                f"{self.base_url}/suggestions/{self.test_user_id}/{self.suggestion_id}/accept",
                headers=self._headers(), timeout=10
            )
            if not self.assert_response(r, 200, should_have=["activity"]):
                raise Exception("Accept failed")
            activity = r.json()["activity"]
            self.activity_id = activity["id"]
            if activity.get("status") != "active":
                raise Exception(f"Expected active status, got {activity.get('status')}")

            # Complete it
            r = requests.patch(
                f"{self.base_url}/activities/{self.test_user_id}/{self.activity_id}",
                json={"status": "completed"},
                headers=self._headers(), timeout=10
            )
            if not self.assert_response(r, 200, should_have=["activity"]):
                raise Exception("Complete failed")
            completed = r.json()["activity"]
            if completed.get("status") != "completed":
                raise Exception("Activity not marked completed")
            if not completed.get("payment_pending"):
                raise Exception("payment_pending not set on priced activity")
            if completed.get("wallet_snapshot") != "0x" + "ab" * 20:
                raise Exception(f"Wallet not snapshotted: {completed.get('wallet_snapshot')}")

            log_success("Activity completed with payment pending and wallet snapshot")
            self.passed += 1
            return True
        except Exception as e:
            log_error(f"Activity flow error: {e}")
        finally:
            # Clean up the test bounty
            if self.bounty_id and DEMAND_API_KEY:
                try:
                    requests.delete(
                        f"{self.base_url}/bounty/{self.bounty_id}",
                        headers=self._api_key_headers(), timeout=10
                    )
                except Exception:
                    pass

        self.failed += 1
        self.errors.append("Activity flow failed")
        return False

    def test_15_delete_user(self):
        """Test self-service account deletion (also cleans up the test user)"""
        log_test("Delete Test User")
        if not self.test_user_id:
            log_error("Skipped - no test user")
            return False

        try:
            r = requests.delete(
                f"{self.base_url}/user/{self.test_user_id}",
                headers=self._headers(), timeout=10
            )
            if not self.assert_response(r, 200, should_have=["ok"]):
                raise Exception("Delete failed")
            # Record should now be gone (401 without valid token, since token was deleted with it)
            r = requests.get(
                f"{self.base_url}/user/{self.test_user_id}",
                headers=self._headers(), timeout=10
            )
            if r.status_code not in (401, 404):
                raise Exception(f"User still accessible after delete: {r.status_code}")
            log_success("Test user deleted and no longer accessible")
            self.passed += 1
            return True
        except Exception as e:
            log_error(f"Delete user error: {e}")

        self.failed += 1
        self.errors.append("User deletion failed")
        return False

    def run_all(self):
        """Run all tests in sequence"""
        print("\n" + "="*60)
        print(f"{Colors.BLUE}GreenDial Integration Test Suite{Colors.END}")
        print(f"Testing: {self.base_url}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # Run tests in order
        tests = [
            self.test_1_ping,
            self.test_2_stats,
            self.test_3_signup,
            self.test_4_login,
            self.test_5_chat,
            self.test_6_profile_update,
            self.test_7_get_user,
            self.test_8_settings,
            self.test_9_conversations,
            self.test_10_notifications,
            self.test_11_auth_enforcement,
            self.test_12_identity_validation,
            self.test_13_bounty_flow,
            self.test_14_activity_flow,
            self.test_15_delete_user
        ]
        
        for test in tests:
            test()
        
        # Summary
        print("\n" + "="*60)
        total = self.passed + self.failed
        print(f"{Colors.BLUE}Test Summary{Colors.END}")
        print(f"  Total:  {total}")
        print(f"  {Colors.GREEN}Passed: {self.passed}{Colors.END}")
        print(f"  {Colors.RED}Failed: {self.failed}{Colors.END}")
        
        if self.errors:
            print(f"\n{Colors.RED}Critical Issues:{Colors.END}")
            for error in self.errors:
                print(f"  • {error}")
        
        print("="*60 + "\n")
        
        # Exit with appropriate code
        sys.exit(0 if self.failed == 0 else 1)


if __name__ == '__main__':
    # Allow custom URL from command line
    url = sys.argv[1] if len(sys.argv) > 1 else BASE_URL
    
    tests = IntegrationTests(url)
    tests.run_all()
