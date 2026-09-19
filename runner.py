import sys
import json
import subprocess
import tempfile
import os

def run_tests(student_code: str, test_cases: list) -> list:
    """
    Executes the student's Python code against the given test cases in a sandboxed subprocess.
    Returns a list of dictionaries with test results.
    """
    # Template for execution script
    exec_template = """import sys
import json
import traceback

# Student code
{student_code}

# Test cases
test_cases = {test_cases}

results = []
for tc in test_cases:
    name = tc['name']
    input_str = tc['input']
    expected_str = tc['expected']
    
    try:
        val = eval(input_str)
        expected = eval(expected_str)
    except Exception as e:
        results.append({{
            "test_name": name,
            "input": input_str,
            "expected": expected_str,
            "actual": f"Test configuration error: {{str(e)}}",
            "passed": False
        }})
        continue
        
    try:
        # Check if the function 'second_largest' is defined
        if 'second_largest' not in globals():
            results.append({{
                "test_name": name,
                "input": input_str,
                "expected": expected_str,
                "actual": "Error: Function 'second_largest' is not defined",
                "passed": False
            }})
            continue
            
        actual = second_largest(val)
        passed = (actual == expected)
        
        results.append({{
            "test_name": name,
            "input": input_str,
            "expected": expected_str,
            "actual": json.dumps(actual),
            "passed": passed
        }})
    except Exception as e:
        # Format the exception beautifully
        exc_type, exc_value, exc_tb = sys.exc_info()
        tb_lines = traceback.format_exception_only(exc_type, exc_value)
        error_msg = "".join(tb_lines).strip()
        results.append({{
            "test_name": name,
            "input": input_str,
            "expected": expected_str,
            "actual": f"Runtime Error: {{error_msg}}",
            "passed": False
        }})

print(json.dumps(results))
"""

    # Populate template
    exec_code = exec_template.format(
        student_code=student_code,
        test_cases=repr(test_cases)
    )

    # Write to a temporary file
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, "bugstriker_sandbox_run.py")
    
    try:
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(exec_code)
            
        # Run subprocess with timeout
        # Using sys.executable to ensure same Python environment is used
        result = subprocess.run(
            [sys.executable, temp_file_path],
            capture_output=True,
            text=True,
            timeout=3.0 # Guard against infinite loops
        )
        
        if result.returncode != 0:
            # Subprocess failed to execute (e.g., syntax error)
            # Try to parse stderr
            stderr_output = result.stderr.strip()
            # If there's a syntax error, let's present it nicely
            actual_error = stderr_output if stderr_output else "Compilation/Execution Error"
            return [
                {
                    "test_name": tc['name'],
                    "input": tc['input'],
                    "expected": tc['expected'],
                    "actual": f"Syntax/Compilation Error: {actual_error}",
                    "passed": False
                }
                for tc in test_cases
            ]
            
        # Try parsing stdout as JSON
        try:
            return json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            # If stdout is not valid JSON, return output as actual
            return [
                {
                    "test_name": tc['name'],
                    "input": tc['input'],
                    "expected": tc['expected'],
                    "actual": f"Output Parse Error: {result.stdout.strip()}",
                    "passed": False
                }
                for tc in test_cases
            ]
            
    except subprocess.TimeoutExpired:
        return [
            {
                "test_name": tc['name'],
                "input": tc['input'],
                "expected": tc['expected'],
                "actual": "Timeout Error: Code execution took too long (infinite loop suspected)",
                "passed": False
            }
            for tc in test_cases
        ]
    except Exception as e:
        return [
            {
                "test_name": tc['name'],
                "input": tc['input'],
                "expected": tc['expected'],
                "actual": f"System Runner Error: {str(e)}",
                "passed": False
            }
            for tc in test_cases
        ]
    finally:
        # Clean up temporary file
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError:
                pass
