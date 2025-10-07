"""Comprehensive tests for Incognito Mode functionality.

Incognito Mode Requirements:
1. Normal Mode: All conversations stored in memory/cache
2. Incognito Mode ON: No new data written to persistent storage, but read access maintained
3. Incognito Mode OFF: Temporary session data cleared, persistent data remains
"""

import pytest
import time
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import List

from server.services.secret_mode import (
    is_incognito_mode_enabled,
    set_incognito_mode,
    get_incognito_mode_status,
    add_to_session_memory,
    get_session_memory,
    clear_session_memory,
    get_session_memory_for_context,
)
from server.services.conversation.log import ConversationLog, get_conversation_log
from server.models.chat import ChatMessage


class TestIncognitoModeBasicFunctions:
    """Test basic incognito mode state management functions."""
    
    def setup_method(self):
        """Reset incognito mode before each test."""
        set_incognito_mode(False)
        clear_session_memory()
    
    def teardown_method(self):
        """Clean up after each test."""
        set_incognito_mode(False)
        clear_session_memory()
    
    def test_incognito_mode_initially_disabled(self):
        """Test that incognito mode is disabled by default."""
        assert not is_incognito_mode_enabled()
    
    def test_enable_incognito_mode(self):
        """Test enabling incognito mode."""
        set_incognito_mode(True)
        assert is_incognito_mode_enabled()
    
    def test_disable_incognito_mode(self):
        """Test disabling incognito mode."""
        set_incognito_mode(True)
        assert is_incognito_mode_enabled()
        
        set_incognito_mode(False)
        assert not is_incognito_mode_enabled()
    
    def test_incognito_mode_status_normal_mode(self):
        """Test status response in normal mode."""
        set_incognito_mode(False)
        status = get_incognito_mode_status()
        
        assert status["paused"] == False
        assert status["ok"] == True
    
    def test_incognito_mode_status_incognito_mode(self):
        """Test status response in incognito mode."""
        set_incognito_mode(True)
        status = get_incognito_mode_status()
        
        assert status["paused"] == True
        assert status["ok"] == True
    
    def test_session_memory_add_and_get(self):
        """Test adding and retrieving session memory."""
        set_incognito_mode(True)
        
        add_to_session_memory("user", "Hello")
        add_to_session_memory("assistant", "Hi there!")
        
        memory = get_session_memory()
        
        assert len(memory) == 2
        assert memory[0]["role"] == "user"
        assert memory[0]["content"] == "Hello"
        assert memory[1]["role"] == "assistant"
        assert memory[1]["content"] == "Hi there!"
        assert "timestamp" in memory[0]
        assert "timestamp" in memory[1]
    
    def test_session_memory_only_in_incognito_mode(self):
        """Test that session memory only stores in incognito mode."""
        set_incognito_mode(False)
        
        add_to_session_memory("user", "This should not be stored")
        
        memory = get_session_memory()
        assert len(memory) == 0
    
    def test_session_memory_cleared_on_disable(self):
        """Test that session memory is cleared when disabling incognito mode."""
        set_incognito_mode(True)
        
        add_to_session_memory("user", "Temporary message")
        add_to_session_memory("assistant", "Temporary response")
        
        memory = get_session_memory()
        assert len(memory) == 2
        
        # Disable incognito mode
        set_incognito_mode(False)
        
        # Session memory should be cleared
        memory = get_session_memory()
        assert len(memory) == 0
    
    def test_clear_session_memory_explicit(self):
        """Test explicitly clearing session memory."""
        set_incognito_mode(True)
        
        add_to_session_memory("user", "Test message")
        assert len(get_session_memory()) == 1
        
        clear_session_memory()
        assert len(get_session_memory()) == 0
    
    def test_session_memory_for_context_format(self):
        """Test that session memory for context has correct format."""
        set_incognito_mode(True)
        
        add_to_session_memory("user", "Hello")
        add_to_session_memory("assistant", "Hi there!")
        
        context = get_session_memory_for_context()
        
        assert len(context) == 2
        assert context[0] == {"role": "user", "content": "Hello"}
        assert context[1] == {"role": "assistant", "content": "Hi there!"}
        # Timestamps should not be in context format
        assert "timestamp" not in context[0]
        assert "timestamp" not in context[1]
    
    def test_session_memory_thread_safety(self):
        """Test that session memory operations are thread-safe."""
        import threading
        
        set_incognito_mode(True)
        errors = []
        
        def add_messages(count: int):
            try:
                for i in range(count):
                    add_to_session_memory("user", f"Message {i}")
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=add_messages, args=(10,)) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        assert len(errors) == 0
        memory = get_session_memory()
        assert len(memory) == 50  # 5 threads * 10 messages


class TestIncognitoModeConversationLog:
    """Test secret mode integration with conversation log."""
    
    def setup_method(self):
        """Set up test environment."""
        set_incognito_mode(False)
        clear_session_memory()
        
        # Create a temporary conversation log
        self.temp_dir = tempfile.mkdtemp()
        self.log_path = Path(self.temp_dir) / "test_conversation.log"
        
        # Create a mock cache that returns empty list
        self.mock_cache = MagicMock()
        self.mock_cache.get_conversation.return_value = []
        
        # Create conversation log and mock its cache
        self.conv_log = ConversationLog(self.log_path)
        self.conv_log._cache = self.mock_cache
    
    def teardown_method(self):
        """Clean up after each test."""
        set_incognito_mode(False)
        clear_session_memory()
        
        # Clean up temporary files
        import shutil
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def test_normal_mode_writes_to_disk(self):
        """Test that normal mode writes messages to disk."""
        set_incognito_mode(False)
        
        self.conv_log.record_user_message("Hello")
        self.conv_log.record_agent_message("Hi there!")
        
        # Check that file exists and has content
        assert self.log_path.exists()
        content = self.log_path.read_text()
        assert "Hello" in content
        assert "Hi there!" in content
    
    def test_incognito_mode_no_disk_writes(self):
        """Test that secret mode does not write to disk."""
        set_incognito_mode(True)
        
        # Ensure file is empty or doesn't exist
        if self.log_path.exists():
            self.log_path.unlink()
        
        self.conv_log.record_user_message("Secret message")
        self.conv_log.record_agent_message("Secret response")
        
        # Check that file either doesn't exist or is empty
        if self.log_path.exists():
            content = self.log_path.read_text()
            assert "Secret message" not in content
            assert "Secret response" not in content
    
    def test_incognito_mode_stores_in_session_memory(self):
        """Test that secret mode stores messages in session memory."""
        set_incognito_mode(True)
        
        self.conv_log.record_user_message("Secret message")
        self.conv_log.record_agent_message("Secret response")
        
        memory = get_session_memory()
        assert len(memory) == 2
        assert memory[0]["content"] == "Secret message"
        assert memory[1]["content"] == "Secret response"
    
    def test_incognito_mode_reads_persistent_data(self):
        """Test that secret mode can read previously stored persistent data."""
        # First, store some data in normal mode
        set_incognito_mode(False)
        self.conv_log.record_user_message("Persistent message")
        self.conv_log.record_reply("Persistent response")
        
        # Verify data was written to disk
        assert self.log_path.exists()
        disk_content = self.log_path.read_text()
        assert "Persistent message" in disk_content
        assert "Persistent response" in disk_content
        
        # Switch to secret mode
        set_incognito_mode(True)
        
        # Add some temporary data
        self.conv_log.record_user_message("Temporary message")
        
        # Get all messages
        messages = self.conv_log.to_chat_messages()
        
        # Should have persistent + session messages
        assert len(messages) >= 3  # At least 2 persistent + 1 session
        
        # Check persistent messages are present
        content_list = [msg.content for msg in messages]
        assert "Persistent message" in content_list
        assert "Persistent response" in content_list
        assert "Temporary message" in content_list
    
    def test_incognito_mode_exit_clears_session_data(self):
        """Test that exiting secret mode clears temporary session data."""
        # First add some persistent data
        set_incognito_mode(False)
        self.conv_log.record_user_message("Initial persistent message")
        
        # Enable secret mode and add data
        set_incognito_mode(True)
        self.conv_log.record_user_message("Temporary message")
        self.conv_log.record_agent_message("Temporary response")
        
        # Verify session memory has data
        assert len(get_session_memory()) == 2
        
        # Verify temporary data is accessible in secret mode
        messages_in_secret = self.conv_log.to_chat_messages()
        secret_contents = [msg.content for msg in messages_in_secret]
        assert "Temporary message" in secret_contents
        assert "Temporary response" in secret_contents
        
        # Disable secret mode
        set_incognito_mode(False)
        
        # Session memory should be cleared
        assert len(get_session_memory()) == 0
        
        # Messages should not include temporary data
        messages = self.conv_log.to_chat_messages()
        content_list = [msg.content for msg in messages]
        assert "Temporary message" not in content_list
        assert "Temporary response" not in content_list
        # But persistent data should still be there
        assert "Initial persistent message" in content_list
    
    def test_mixed_mode_scenario(self):
        """Test a complete scenario with mode switching."""
        # Step 1: Normal mode - store initial data
        set_incognito_mode(False)
        self.conv_log.record_user_message("My favorite color is blue")
        self.conv_log.record_reply("I'll remember that your favorite color is blue.")
        
        # Step 2: Enable secret mode
        set_incognito_mode(True)
        
        # Step 3: Ask about stored data (should be accessible)
        messages = self.conv_log.to_chat_messages()
        content_list = [msg.content for msg in messages]
        assert "My favorite color is blue" in content_list
        
        # Step 4: Store temporary data
        self.conv_log.record_user_message("My favorite number is 6")
        self.conv_log.record_agent_message("Noted.")
        
        # Step 5: Verify both persistent and session data accessible
        messages = self.conv_log.to_chat_messages()
        content_list = [msg.content for msg in messages]
        assert "My favorite color is blue" in content_list
        assert "My favorite number is 6" in content_list
        
        # Step 6: Exit secret mode
        set_incognito_mode(False)
        
        # Step 7: Verify only persistent data remains
        messages = self.conv_log.to_chat_messages()
        content_list = [msg.content for msg in messages]
        assert "My favorite color is blue" in content_list
        assert "My favorite number is 6" not in content_list
        
        # Step 8: Add new data in normal mode (should persist)
        self.conv_log.record_user_message("My name is Alice")
        
        # Step 9: Verify new data persisted
        messages = self.conv_log.to_chat_messages()
        content_list = [msg.content for msg in messages]
        assert "My name is Alice" in content_list
    
    def test_record_reply_in_incognito_mode(self):
        """Test that record_reply also respects secret mode."""
        set_incognito_mode(True)
        
        # Ensure file is empty or doesn't exist
        if self.log_path.exists():
            self.log_path.unlink()
        
        self.conv_log.record_reply("Secret reply")
        
        # Check that file either doesn't exist or doesn't contain the reply
        if self.log_path.exists():
            content = self.log_path.read_text()
            assert "Secret reply" not in content
        
        # Check that it's in session memory
        memory = get_session_memory()
        assert len(memory) == 1
        assert memory[0]["content"] == "Secret reply"


class TestIncognitoModeWorkingMemory:
    """Test secret mode integration with working memory log."""
    
    def setup_method(self):
        """Set up test environment."""
        set_incognito_mode(False)
        clear_session_memory()
        
        # Create a temporary conversation log
        self.temp_dir = tempfile.mkdtemp()
        self.log_path = Path(self.temp_dir) / "test_conversation.log"
        
        # Create a mock working memory log
        self.mock_working_memory = MagicMock()
        
        # Patch working memory log resolution
        self.working_memory_patcher = patch(
            'server.services.conversation.log._resolve_working_memory_log',
            return_value=self.mock_working_memory
        )
        self.working_memory_patcher.start()
        
        self.conv_log = ConversationLog(self.log_path)
    
    def teardown_method(self):
        """Clean up after each test."""
        set_incognito_mode(False)
        clear_session_memory()
        self.working_memory_patcher.stop()
        
        # Clean up temporary files
        import shutil
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def test_normal_mode_updates_working_memory(self):
        """Test that normal mode updates working memory."""
        set_incognito_mode(False)
        
        self.conv_log.record_user_message("Test message")
        
        # Working memory should be updated
        self.mock_working_memory.append_entry.assert_called_once()
        call_args = self.mock_working_memory.append_entry.call_args
        assert call_args[0][0] == "user_message"
        assert call_args[0][1] == "Test message"
    
    def test_incognito_mode_no_working_memory_updates(self):
        """Test that secret mode does not update working memory."""
        set_incognito_mode(True)
        
        self.conv_log.record_user_message("Secret message")
        
        # Working memory should NOT be updated
        self.mock_working_memory.append_entry.assert_not_called()


class TestIncognitoModeThreadSafety:
    """Test thread safety of secret mode operations."""
    
    def setup_method(self):
        """Reset secret mode before each test."""
        set_incognito_mode(False)
        clear_session_memory()
    
    def teardown_method(self):
        """Clean up after each test."""
        set_incognito_mode(False)
        clear_session_memory()
    
    def test_concurrent_mode_changes(self):
        """Test that concurrent mode changes are thread-safe."""
        import threading
        errors = []
        
        def toggle_mode(count: int):
            try:
                for i in range(count):
                    set_incognito_mode(i % 2 == 0)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=toggle_mode, args=(20,)) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        assert len(errors) == 0
        # Just verify it's in a valid state (either True or False)
        assert isinstance(is_incognito_mode_enabled(), bool)
    
    def test_concurrent_session_memory_operations(self):
        """Test concurrent session memory operations."""
        import threading
        errors = []
        
        set_incognito_mode(True)
        
        def add_and_clear(id: int):
            try:
                for i in range(10):
                    add_to_session_memory("user", f"Thread {id} message {i}")
                    if i % 3 == 0:
                        get_session_memory()
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=add_and_clear, args=(i,)) for i in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        assert len(errors) == 0


class TestIncognitoModeEdgeCases:
    """Test edge cases and boundary conditions for secret mode."""
    
    def setup_method(self):
        """Reset secret mode before each test."""
        set_incognito_mode(False)
        clear_session_memory()
    
    def teardown_method(self):
        """Clean up after each test."""
        set_incognito_mode(False)
        clear_session_memory()
    
    def test_empty_message_in_incognito_mode(self):
        """Test handling of empty messages in secret mode."""
        set_incognito_mode(True)
        
        add_to_session_memory("user", "")
        memory = get_session_memory()
        
        assert len(memory) == 1
        assert memory[0]["content"] == ""
    
    def test_large_message_in_incognito_mode(self):
        """Test handling of large messages in secret mode."""
        set_incognito_mode(True)
        
        large_message = "A" * 100000  # 100KB message
        add_to_session_memory("user", large_message)
        
        memory = get_session_memory()
        assert len(memory) == 1
        assert memory[0]["content"] == large_message
    
    def test_special_characters_in_session_memory(self):
        """Test handling of special characters in session memory."""
        set_incognito_mode(True)
        
        special_message = "Test with <tags> & \"quotes\" and 'apostrophes' \n newlines \t tabs"
        add_to_session_memory("user", special_message)
        
        memory = get_session_memory()
        assert len(memory) == 1
        assert memory[0]["content"] == special_message
    
    def test_multiple_mode_switches(self):
        """Test multiple rapid mode switches."""
        for i in range(10):
            set_incognito_mode(i % 2 == 0)
            
            if is_incognito_mode_enabled():
                add_to_session_memory("user", f"Message {i}")
        
        # Should end with secret mode disabled and empty session memory
        assert not is_incognito_mode_enabled()
        assert len(get_session_memory()) == 0
    
    def test_session_memory_persistence_across_enable(self):
        """Test that session memory persists when re-enabling secret mode."""
        # This is actually the correct behavior - session memory should clear
        # when disabling secret mode, so re-enabling gives a fresh start
        set_incognito_mode(True)
        add_to_session_memory("user", "First message")
        set_incognito_mode(False)
        set_incognito_mode(True)
        
        memory = get_session_memory()
        assert len(memory) == 0  # Should be cleared
    
    def test_custom_timestamp_in_session_memory(self):
        """Test adding messages with custom timestamps."""
        set_incognito_mode(True)
        
        custom_timestamp = "2024-01-01 12:00:00"
        add_to_session_memory("user", "Test message", timestamp=custom_timestamp)
        
        memory = get_session_memory()
        assert len(memory) == 1
        assert memory[0]["timestamp"] == custom_timestamp


class TestIncognitoModeIntegration:
    """Integration tests for secret mode with the full system."""
    
    def setup_method(self):
        """Set up test environment."""
        set_incognito_mode(False)
        clear_session_memory()
    
    def teardown_method(self):
        """Clean up after each test."""
        set_incognito_mode(False)
        clear_session_memory()
    
    def test_incognito_mode_status_endpoint_behavior(self):
        """Test the status endpoint returns correct information."""
        # Normal mode
        set_incognito_mode(False)
        status = get_incognito_mode_status()
        assert status["paused"] == False
        assert status["ok"] == True
        
        # Secret mode
        set_incognito_mode(True)
        status = get_incognito_mode_status()
        assert status["paused"] == True
        assert status["ok"] == True
    
    def test_complete_user_workflow(self):
        """Test a complete user workflow with secret mode."""
        temp_dir = tempfile.mkdtemp()
        log_path = Path(temp_dir) / "workflow_test.log"
        conv_log = ConversationLog(log_path)
        
        # Mock the cache to avoid accessing global conversation log
        mock_cache = MagicMock()
        mock_cache.get_conversation.return_value = []
        conv_log._cache = mock_cache
        
        try:
            # Phase 1: Normal usage - store personal information
            set_incognito_mode(False)
            conv_log.record_user_message("My favorite color is blue")
            conv_log.record_reply("Got it, your favorite color is blue!")
            
            # Verify it was written to disk
            assert log_path.exists()
            disk_content = log_path.read_text()
            assert "favorite color is blue" in disk_content
            
            # Phase 2: Enable secret mode
            set_incognito_mode(True)
            
            # Phase 3: User can still access stored information
            messages = conv_log.to_chat_messages()
            contents = [msg.content for msg in messages]
            assert "My favorite color is blue" in contents
            
            # Phase 4: User shares sensitive information (not stored)
            conv_log.record_user_message("My credit card number is 1234")
            conv_log.record_reply("I understand (not saved)")
            
            # Verify it's in session memory but not on disk
            session = get_session_memory()
            session_contents = [msg["content"] for msg in session]
            assert "credit card number" in str(session_contents)
            
            disk_content = log_path.read_text()
            assert "credit card" not in disk_content
            
            # Phase 5: Disable secret mode
            set_incognito_mode(False)
            
            # Phase 6: Session data should be gone
            messages = conv_log.to_chat_messages()
            contents = [msg.content for msg in messages]
            assert "My favorite color is blue" in contents  # Persistent data remains
            assert "credit card" not in str(contents)  # Temporary data gone
            
            # Phase 7: New information stored normally
            conv_log.record_user_message("My name is Alice")
            conv_log.record_reply("Nice to meet you, Alice!")
            
            disk_content = log_path.read_text()
            assert "name is Alice" in disk_content
            
        finally:
            # Cleanup
            import shutil
            if Path(temp_dir).exists():
                shutil.rmtree(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

