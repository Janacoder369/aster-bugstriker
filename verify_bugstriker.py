import sys
import os
import json

# Resolve paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

import runner
import evaluator
import app

def test_rubric_load():
    print("Testing rubric loading...")
    rubric = app.load_rubric()
    assert rubric["problem_id"] == "second_largest"
    assert len(rubric["test_cases"]) == 3
    print("✓ Rubric load verified.")

def test_runner_flawed_code():
    print("Testing test runner with flawed code...")
    flawed_code = """
def second_largest(a):
    a.sort()
    return a[-2]
"""
    rubric = app.load_rubric()
    results = runner.run_tests(flawed_code, rubric["test_cases"])
    
    # [5, 1, 9, 3] -> expected 5, sorted unique is 5, sorted with original is 5.
    case_1 = next(r for r in results if r["test_name"] == "case_1_distinct")
    assert case_1["passed"] == True
    
    # [5, 5, 2] -> expected 2, but sorted [-2] is 5.
    case_2 = next(r for r in results if r["test_name"] == "case_2_duplicates")
    assert case_2["passed"] == False
    
    print("✓ Runner verification with flawed code matches expectation.")

def test_runner_correct_code():
    print("Testing test runner with correct code...")
    correct_code = """
def second_largest(a):
    values = sorted(set(a))
    if len(values) < 2:
        return "invalid input"
    return values[-2]
"""
    rubric = app.load_rubric()
    results = runner.run_tests(correct_code, rubric["test_cases"])
    
    # All cases should pass
    for r in results:
        assert r["passed"] == True, f"Failed case {r['test_name']}"
        
    print("✓ Runner verification with correct code matches expectation.")

def test_evaluator_explanation():
    print("Testing evaluator explanations...")
    rubric = app.load_rubric()
    
    # Correct explanation
    good_answer = "I need to remove duplicates first, perhaps using a set."
    eval_good = evaluator.evaluate_explanation(good_answer, "case_2_duplicates", rubric)
    assert eval_good["passed"] == True
    assert "duplicate" in eval_good["matched_keywords"]
    
    # Incorrect explanation
    bad_answer = "I need to multiply by two."
    eval_bad = evaluator.evaluate_explanation(bad_answer, "case_2_duplicates", rubric)
    assert eval_bad["passed"] == False
    assert len(eval_bad["matched_keywords"]) == 0
    
    print("✓ Explanation evaluation keyword check verified.")

def run_all_checks():
    print("=================== BUGSTRIKER SYSTEM CHECK ===================")
    try:
        test_rubric_load()
        test_runner_flawed_code()
        test_runner_correct_code()
        test_evaluator_explanation()
        print("=================== ALL VERIFICATIONS PASSED! ===================")
    except AssertionError as e:
        print(f"❌ Verification failed: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected system error during verification: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    run_all_checks()
