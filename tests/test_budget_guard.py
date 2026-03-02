import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock
import pytest

# Add the shared/scripts directory to the path so we can import the modules
sys.path.insert(0, os.path.join(os.path.expanduser('~/.openclaw/workspace'), 'shared/scripts'))

# Import the modules we need to test
import provider_budget_guard
import manager_cooldown


def test_provider_mapping():
    """Verify model names map to correct providers"""
    # Test anthropic models
    assert provider_budget_guard.map_model_to_provider('anthropic/claude-3-opus-20240229') == 'anthropic'
    assert provider_budget_guard.map_model_to_provider('anthropic/claude-3-sonnet-20240229') == 'anthropic'
    
    # Test qwen models
    assert provider_budget_guard.map_model_to_provider('qwen/qwen-plus') == 'qwen'
    assert provider_budget_guard.map_model_to_provider('qwen/qwen-max') == 'qwen'
    
    # Test google models
    assert provider_budget_guard.map_model_to_provider('google/gemini-pro') == 'google'
    assert provider_budget_guard.map_model_to_provider('google/gemini-ultra') == 'google'
    
    # Test unknown models
    assert provider_budget_guard.map_model_to_provider('unknown/model') == 'unknown'


def test_warn_threshold():
    """Mock GCP returning 0.91 of cap → status=warn"""
    # Mock the GCP query result to return 0.91 for anthropic (91% of $1.00 cap)
    mock_results = [
        ('anthropic/claude-3-opus-20240229', 0.91),
        ('qwen/qwen-plus', 0.25),
        ('google/gemini-pro', 0.15)
    ]
    
    with patch('provider_budget_guard.gcp_client') as mock_gcp:
        mock_gcp.query.return_value = mock_results
        
        # Create a temporary file for the output
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        # Run the main function with the temp file path
        try:
            provider_budget_guard.main(output_file=tmp_path)
            
            # Read the output file
            with open(tmp_path, 'r') as f:
                result = json.load(f)
            
            # Check that anthropic is in warn_providers
            assert 'anthropic' in result['warn_providers']
            assert result['anthropic']['status'] == 'warn'
            assert result['anthropic']['spent'] == 0.91
            
        finally:
            # Clean up the temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


def test_hard_stop():
    """Mock GCP returning 1.01 of cap → hard_stop_providers contains provider, exit 1"""
    # Mock the GCP query result to return 1.01 for anthropic (over $1.00 cap)
    mock_results = [
        ('anthropic/claude-3-opus-20240229', 1.01),
        ('qwen/qwen-plus', 0.25),
        ('google/gemini-pro', 0.15)
    ]
    
    with patch('provider_budget_guard.gcp_client') as mock_gcp:
        mock_gcp.query.return_value = mock_results
        
        # Create a temporary file for the output
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        # Run the main function with the temp file path
        try:
            # Capture the exit code
            exit_code = provider_budget_guard.main(output_file=tmp_path)
            
            # Read the output file
            with open(tmp_path, 'r') as f:
                result = json.load(f)
            
            # Check that anthropic is in hard_stop_providers
            assert 'anthropic' in result['hard_stop_providers']
            assert result['anthropic']['status'] == 'hard_stop'
            assert result['anthropic']['spent'] == 1.01
            
            # Check that exit code is 1
            assert exit_code == 1
            
        finally:
            # Clean up the temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


def test_cooldown_same_type():
    """Call cooldown with same type within 30min → returns cooldown=true"""
    # Create a test bot_cache.json with recent report
    test_cache = {
        "manager": {
            "last_report_type": "team_brief",
            "last_report_ts": 1703275200  # A recent timestamp (within last 30 minutes)
        }
    }
    
    # Write test cache to a temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
        json.dump(test_cache, tmp_file)
        tmp_cache_path = tmp_file.name
    
    try:
        # Mock sys.stdin to provide input
        import io
        original_stdin = sys.stdin
        
        # Create input JSON
        input_json = '{"report_type":"team_brief","metrics_hash":"abc123"}'
        sys.stdin = io.StringIO(input_json)
        
        # Run the manager_cooldown script
        with patch('manager_cooldown.BOT_CACHE_PATH', tmp_cache_path):
            # Capture stdout
            from io import StringIO
            old_stdout = sys.stdout
            captured_output = StringIO()
            sys.stdout = captured_output
            
            try:
                # This will call sys.exit() with code 1, so we need to catch it
                try:
                    manager_cooldown.main()
                except SystemExit as e:
                    if e.code != 1:
                        raise e
                    
                # Get the output
                output = captured_output.getvalue()
                
                # Parse the JSON output
                result = json.loads(output.strip())
                
                # Check that cooldown is true
                assert result['cooldown'] == True
                assert result['reason'] == 'same report within 30min'
                
            finally:
                sys.stdout = old_stdout
                
    finally:
        # Clean up the temp file
        if os.path.exists(tmp_cache_path):
            os.unlink(tmp_cache_path)
        sys.stdin = original_stdin


def test_cooldown_delta():
    """Call with delta → returns cooldown=false"""
    # Create a test bot_cache.json with different report type
    test_cache = {
        "manager": {
            "last_report_type": "market_brief",
            "last_report_ts": 1703275200  # A recent timestamp
        }
    }
    
    # Write test cache to a temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
        json.dump(test_cache, tmp_file)
        tmp_cache_path = tmp_file.name
    
    try:
        # Mock sys.stdin to provide input
        import io
        original_stdin = sys.stdin
        
        # Create input JSON
        input_json = '{"report_type":"team_brief","metrics_hash":"abc123"}'
        sys.stdin = io.StringIO(input_json)
        
        # Run the manager_cooldown script
        with patch('manager_cooldown.BOT_CACHE_PATH', tmp_cache_path):
            # Capture stdout
            from io import StringIO
            old_stdout = sys.stdout
            captured_output = StringIO()
            sys.stdout = captured_output
            
            try:
                # This will call sys.exit() with code 0, so we need to catch it
                try:
                    manager_cooldown.main()
                except SystemExit as e:
                    if e.code != 0:
                        raise e
                    
                # Get the output
                output = captured_output.getvalue()
                
                # Parse the JSON output
                result = json.loads(output.strip())
                
                # Check that cooldown is false
                assert result['cooldown'] == False
                
            finally:
                sys.stdout = old_stdout
                
    finally:
        # Clean up the temp file
        if os.path.exists(tmp_cache_path):
            os.unlink(tmp_cache_path)
        sys.stdin = original_stdin

if __name__ == "__main__":
    pytest.main(["-v", __file__])
