"""Tests for Incognito Mode API endpoints."""

import pytest
from fastapi.testclient import TestClient

from server.app import app
from server.services.secret_mode import (
    set_incognito_mode,
    is_incognito_mode_enabled,
    clear_session_memory,
)


class TestIncognitoModeAPIEndpoints:
    """Test Incognito Mode API endpoints."""
    
    def setup_method(self):
        """Set up test environment."""
        self.client = TestClient(app)
        set_incognito_mode(False)
        clear_session_memory()
    
    def teardown_method(self):
        """Clean up after each test."""
        set_incognito_mode(False)
        clear_session_memory()
    
    def test_memory_status_normal_mode(self):
        """Test /chat/memory/status endpoint returns correct status in normal mode."""
        set_incognito_mode(False)
        
        response = self.client.get("/api/v1/chat/memory/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["paused"] == False
        assert data["ok"] == True
    
    def test_memory_status_incognito_mode(self):
        """Test /chat/memory/status endpoint returns correct status in secret mode."""
        set_incognito_mode(True)
        
        response = self.client.get("/api/v1/chat/memory/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["paused"] == True
        assert data["ok"] == True
    
    def test_memory_pause_endpoint(self):
        """Test /chat/memory/pause endpoint enables secret mode."""
        # Ensure we start in normal mode
        set_incognito_mode(False)
        assert not is_incognito_mode_enabled()
        
        # Call pause endpoint
        response = self.client.post("/api/v1/chat/memory/pause")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "Incognito mode enabled" in data["message"]
        
        # Verify incognito mode is now enabled
        assert is_incognito_mode_enabled()
    
    def test_memory_resume_endpoint(self):
        """Test /chat/memory/resume endpoint disables secret mode."""
        # Enable secret mode first
        set_incognito_mode(True)
        assert is_incognito_mode_enabled()
        
        # Call resume endpoint
        response = self.client.post("/api/v1/chat/memory/resume")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "Incognito mode disabled" in data["message"]
        
        # Verify incognito mode is now disabled
        assert not is_incognito_mode_enabled()
    
    def test_memory_pause_resume_cycle(self):
        """Test pausing and resuming memory multiple times."""
        # Start in normal mode
        set_incognito_mode(False)
        
        # Pause
        response = self.client.post("/api/v1/chat/memory/pause")
        assert response.status_code == 200
        assert is_incognito_mode_enabled()
        
        # Check status
        response = self.client.get("/api/v1/chat/memory/status")
        assert response.json()["paused"] == True
        
        # Resume
        response = self.client.post("/api/v1/chat/memory/resume")
        assert response.status_code == 200
        assert not is_incognito_mode_enabled()
        
        # Check status again
        response = self.client.get("/api/v1/chat/memory/status")
        assert response.json()["paused"] == False
        
        # Pause again
        response = self.client.post("/api/v1/chat/memory/pause")
        assert response.status_code == 200
        assert is_incognito_mode_enabled()
    
    def test_memory_reset_clears_session_memory(self):
        """Test that /chat/memory/reset also clears session memory."""
        # Enable secret mode and add session data
        set_incognito_mode(True)
        from server.services.secret_mode import add_to_session_memory, get_session_memory
        
        add_to_session_memory("user", "Test message")
        assert len(get_session_memory()) == 1
        
        # Call reset endpoint
        response = self.client.post("/api/v1/chat/memory/reset")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        
        # Verify session memory is cleared
        assert len(get_session_memory()) == 0
    
    def test_api_endpoint_idempotency(self):
        """Test that calling pause/resume multiple times is safe."""
        # Pause twice
        response1 = self.client.post("/api/v1/chat/memory/pause")
        response2 = self.client.post("/api/v1/chat/memory/pause")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert is_incognito_mode_enabled()
        
        # Resume twice
        response3 = self.client.post("/api/v1/chat/memory/resume")
        response4 = self.client.post("/api/v1/chat/memory/resume")
        
        assert response3.status_code == 200
        assert response4.status_code == 200
        assert not is_incognito_mode_enabled()


class TestIncognitoModeAPIIntegration:
    """Integration tests for Incognito Mode API with conversation flow."""
    
    def setup_method(self):
        """Set up test environment."""
        self.client = TestClient(app)
        set_incognito_mode(False)
        clear_session_memory()
    
    def teardown_method(self):
        """Clean up after each test."""
        set_incognito_mode(False)
        clear_session_memory()
    
    def test_status_reflects_mode_changes(self):
        """Test that status endpoint immediately reflects mode changes."""
        # Check initial status
        response = self.client.get("/api/v1/chat/memory/status")
        assert response.json()["paused"] == False
        
        # Pause memory
        self.client.post("/api/v1/chat/memory/pause")
        
        # Status should immediately reflect the change
        response = self.client.get("/api/v1/chat/memory/status")
        assert response.json()["paused"] == True
        
        # Resume memory
        self.client.post("/api/v1/chat/memory/resume")
        
        # Status should immediately reflect the change
        response = self.client.get("/api/v1/chat/memory/status")
        assert response.json()["paused"] == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

